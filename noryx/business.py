"""All monetary transitions happen on the server within one transaction."""
from calendar import monthrange
from datetime import datetime
from flask import abort
from sqlalchemy.exc import IntegrityError
from .models import *
from .security import audit

CYCLES={'monthly':1,'quarterly':3,'semiannual':6,'annual':12}
def add_months(date, months):
    month=date.month-1+months
    year=date.year+month//12
    month=month%12+1
    return date.replace(year=year,month=month,day=min(date.day,monthrange(year,month)[1]))

def snapshot(plan,price):
    return {'name':plan.name,'category':plan.category.name,
        'location':plan.location.name if plan.location else None,
        'processor':plan.processor.name if plan.processor else None,
        'specifications':plan.specifications,'revision':plan.revision,
        'cycle':price.cycle,'amount':price.amount,'setup_fee':price.setup_fee,'currency':price.currency}

def place_order(user_id, price_id, key, coupon_code=''):
    if not key or len(key)>64: abort(400,'Invalid checkout key.')
    existing=db.session.scalar(db.select(Order).where(Order.user_id==user_id,Order.idempotency_key==key))
    if existing: return existing
    price=db.session.get(PlanPrice,price_id)
    if not price: abort(404)
    plan=db.session.scalar(db.select(Plan).where(Plan.id==price.plan_id).with_for_update())
    if plan.status!='published' or plan.stock<1: abort(409,'This plan is not currently available.')
    if (plan.location and not plan.location.active) or (plan.processor and not plan.processor.active): abort(409,'Hardware availability requires review.')
    # Compare-and-update also prevents overselling on SQLite, which lacks row locks.
    changed=db.session.execute(db.update(Plan).where(Plan.id==plan.id,Plan.stock>0,Plan.status=='published').values(stock=Plan.stock-1))
    if not changed.rowcount: abort(409,'Out of stock.')
    total=price.amount+price.setup_fee
    saved=snapshot(plan,price)
    if coupon_code:
        coupon=db.session.scalar(db.select(Coupon).where(Coupon.code==coupon_code.upper()).with_for_update())
        if not coupon or coupon.expires_at<=now() or coupon.uses>=coupon.max_uses or (coupon.category_id and coupon.category_id!=plan.category_id):
            db.session.rollback(); abort(400,'Coupon is unavailable for this plan.')
        changed=db.session.execute(db.update(Coupon).where(Coupon.id==coupon.id,Coupon.uses<Coupon.max_uses).values(uses=Coupon.uses+1))
        if not changed.rowcount: db.session.rollback(); abort(409,'Coupon limit reached.')
        discount=price.amount*coupon.percent//100
        total-=discount
        saved.update(coupon=coupon.code,discount=discount)
    order=Order(user_id=user_id,plan_id=plan.id,idempotency_key=key,snapshot=saved,total=total,currency=price.currency)
    try:
        db.session.add(order); db.session.flush()
        db.session.add(Invoice(order_id=order.id,user_id=user_id,total=total,currency=price.currency))
        audit('order.created',order.id)
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        existing=db.session.scalar(db.select(Order).where(Order.user_id==user_id,Order.idempotency_key==key))
        if existing: return existing
        raise
    return order

def record_manual_payment(invoice_id, reference, actor_id):
    invoice=db.session.scalar(db.select(Invoice).where(Invoice.id==invoice_id).with_for_update())
    if not invoice: abort(404)
    if invoice.status!='unpaid': abort(409,'Invoice is not unpaid.')
    if not reference or len(reference)>150: abort(400,'A verified external payment reference is required.')
    if db.session.scalar(db.select(Payment.id).where(Payment.reference==reference)): abort(409,'Payment reference already recorded.')
    order=db.session.scalar(db.select(Order).where(Order.id==invoice.order_id).with_for_update())
    if order.status!='awaiting_payment': abort(409,'Order cannot accept payment.')
    changed=db.session.execute(db.update(Invoice).where(Invoice.id==invoice_id,Invoice.status=='unpaid').values(status='paid'))
    if not changed.rowcount: abort(409,'Invoice changed; reload before continuing.')
    db.session.add(Payment(invoice_id=invoice.id,reference=reference,amount=invoice.total,currency=invoice.currency,actor_id=actor_id))
    order.status='paid'; audit('payment.manual_verified',f'invoice={invoice.id}; reference={reference}')
    try: db.session.commit()
    except IntegrityError: db.session.rollback(); abort(409,'Payment already recorded.')

def fulfill(order_id, reference):
    order=db.session.scalar(db.select(Order).where(Order.id==order_id).with_for_update())
    if not order: abort(404)
    if order.status!='paid': abort(409,'Only verified, paid orders can be fulfilled.')
    if not reference or len(reference)>200: abort(400,'Enter the actual fulfillment reference.')
    changed=db.session.execute(db.update(Order).where(Order.id==order_id,Order.status=='paid').values(status='active'))
    if not changed.rowcount: abort(409,'Order changed; reload before continuing.')
    db.session.add(Service(order_id=order.id,user_id=order.user_id,next_due=add_months(now(),CYCLES[order.snapshot['cycle']]),fulfillment_reference=reference))
    audit('order.manually_fulfilled',f'order={order.id}; reference={reference}')
    try: db.session.commit()
    except IntegrityError: db.session.rollback(); abort(409,'Order already fulfilled.')

def cancel_order(order_id,user_id):
    order=db.session.scalar(db.select(Order).where(Order.id==order_id,Order.user_id==user_id).with_for_update())
    if not order: abort(404)
    changed=db.session.execute(db.update(Order).where(Order.id==order_id,Order.status=='awaiting_payment').values(status='cancelled'))
    if not changed.rowcount: abort(409,'Only unpaid orders can be cancelled here.')
    db.session.execute(db.update(Plan).where(Plan.id==order.plan_id).values(stock=Plan.stock+1))
    db.session.execute(db.update(Invoice).where(Invoice.order_id==order_id).values(status='void'))
    audit('order.cancelled',order_id); db.session.commit()
