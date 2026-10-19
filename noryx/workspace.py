"""Workspace views backed by existing billing and service records."""
from collections import Counter
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from flask import Blueprint, abort, current_app, g, request, render_template, redirect, flash
from sqlalchemy import func
from .models import *
from .security import required, reauthenticate, audit, PERMISSIONS
from .routes import textfield, integer, rows
from .business import add_months, cancel_order

workspace=Blueprint('workspace',__name__)
CURRENCIES=('INR','USD','EUR','GBP')
def preference(key,default=None):
    setting=db.session.get(WorkspaceSetting,key)
    return setting.value if setting else default

def dashboard_metrics():
    currency=request.args.get('currency',preference('currency','INR'))
    if currency not in CURRENCIES: currency='INR'
    start=add_months(now().replace(day=1,hour=0,minute=0,second=0,microsecond=0),-6)
    months=[add_months(start,i) for i in range(7)]
    payments=db.session.scalars(db.select(Payment).where(Payment.currency==currency,Payment.created_at>=start)).all()
    values=[sum(p.amount for p in payments if (p.created_at.year,p.created_at.month)==(m.year,m.month)) for m in months]
    maximum=max(max(values),100)
    points=[(50+i*80,190-150*value/maximum) for i,value in enumerate(values)]
    revenue_path=' '.join(('M' if i==0 else 'L')+f'{x:.1f},{y:.1f}' for i,(x,y) in enumerate(points))
    counts=Counter(service.order.snapshot.get('category','Other') for service in db.session.scalars(db.select(Service).where(Service.status=='active')))
    total=sum(counts.values()); categories=[]; offset=0
    for index,(name,count) in enumerate(counts.most_common()):
        share=count/total*100
        categories.append(dict(name=name,count=count,share=share,offset=-offset,color=['#facc15','#60a5fa','#22d3ee','#a78bfa','#94a3b8'][index%5]));offset+=share
    return dict(currency=currency,months=months,values=values,revenue_path=revenue_path,period_revenue=sum(values),total_revenue=db.session.scalar(db.select(func.coalesce(func.sum(Payment.amount),0)).where(Payment.currency==currency)),categories=categories,service_total=total,recent_activity=rows(Audit,7))

@workspace.get('/admin/analytics')
@required('audit')
def analytics(): return render_template('analytics.html',title='Analytics',**dashboard_metrics())

@workspace.get('/client/announcements')
@required()
def announcements():
    items=db.session.scalars(db.select(Announcement).where(Announcement.archived.is_(False),Announcement.publish_at<=now()).order_by(Announcement.pinned.desc(),Announcement.publish_at.desc())).all()
    return render_template('announcements.html',title='Announcements',items=items)

@workspace.route('/admin/settings',methods=['GET','POST'])
@required('audit')
def settings():
    tab=request.args.get('tab','general')
    if tab not in ('general','payments','email','security','appearance','integrations'): abort(404)
    if request.method=='POST':
        if g.user.role!='super_admin': abort(403,'Only a Super Admin can change workspace settings.')
        reauthenticate(); values={}
        if tab=='general':
            url=textfield('public_url',500); parsed=urlsplit(url)
            if parsed.scheme not in ('https','http') or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment: abort(400,'Enter a public HTTP or HTTPS URL without credentials, query or fragment.')
            zone=textfield('timezone',100)
            try: ZoneInfo(zone)
            except (ZoneInfoNotFoundError,ValueError): abort(400,'Unknown timezone.')
            currency=textfield('currency',3)
            if currency not in CURRENCIES: abort(400,'Unsupported currency.')
            values=dict(site_name=textfield('site_name',100),public_url=url.rstrip('/'),timezone=zone,currency=currency)
        elif tab=='security': values={'registration_open':request.form.get('registration_open')=='on'}
        elif tab=='appearance':
            logo=request.form.get('logo_path')
            if logo!='/assets/brand/noryx-logo.png': abort(400,'Choose an approved brand asset.')
            values={'logo_path':logo}
        else: abort(400,'Provider credentials are configured in the server environment.')
        for key,value in values.items():
            setting=db.session.get(WorkspaceSetting,key)
            if setting: setting.value=value
            else: db.session.add(WorkspaceSetting(key=key,value=value))
        audit('workspace.settings',','.join(values)); db.session.commit(); flash('Settings saved.')
        return redirect(request.full_path)
    return render_template('settings.html',title='Workspace settings',tab=tab,settings={k:preference(k,v) for k,v in dict(site_name='Noryx Hosting',public_url=current_app.config['PUBLIC_URL'],timezone='UTC',currency='INR',registration_open=True,logo_path='/assets/brand/noryx-logo.png').items()})

@workspace.route('/admin/addons',methods=['GET','POST'])
@required('catalog')
def addons():
    if request.method=='POST':
        ident=request.form.get('id',type=int); item=db.get_or_404(PlanAddon,ident) if ident else PlanAddon()
        currency=textfield('currency',3)
        if currency not in CURRENCIES: abort(400)
        item.name=textfield('name',100);item.description=textfield('description',500,True);item.amount=integer('amount');item.currency=currency;item.active=request.form.get('active')=='on'
        db.session.add(item);audit('addon.saved');db.session.commit();return redirect(request.path)
    return render_template('addons.html',title='Add-on definitions',items=rows(PlanAddon))

@workspace.get('/admin/order/<int:ident>')
@required('billing')
def order_detail(ident):
    order=db.get_or_404(Order,ident); invoice=db.session.scalar(db.select(Invoice).where(Invoice.order_id==ident))
    payment=db.session.scalar(db.select(Payment).where(Payment.invoice_id==invoice.id)) if invoice else None
    return render_template('admin_order.html',title=f'Order #{ident}',order=order,invoice=invoice,payment=payment)

@workspace.post('/admin/orders/<int:ident>/cancel')
@required('billing')
def reject_order(ident):
    reauthenticate(); order=db.get_or_404(Order,ident)
    if order.status!='awaiting_payment': abort(409,'Only unpaid orders can be rejected.')
    cancel_order(order.id,order.user_id);flash('Unpaid order rejected and reserved stock released.');return redirect('/admin/orders')

@workspace.get('/admin/<section>')
@required()
def operations(section):
    permissions={'locations':'catalog','processors':'catalog','stock':'catalog','invoices':'billing','transactions':'billing','refunds':'billing','infrastructure':'audit','provisioning':'audit','monitoring':'audit','health':'audit','staff':'users','media':'content'}
    if section not in permissions: abort(404)
    if permissions[section] not in PERMISSIONS[g.user.role]: abort(403)
    models={'locations':Location,'processors':Processor,'stock':Plan,'invoices':Invoice,'transactions':Payment}
    items=rows(models[section]) if section in models else []
    if section=='staff': items=db.session.scalars(db.select(User).where(User.role!='client',User.deleted_at.is_(None))).all()
    if section=='provisioning': items=db.session.scalars(db.select(Order).where(Order.status=='paid')).all()
    jobs={state:db.session.scalar(db.select(func.count()).select_from(EmailJob).where(EmailJob.state==state)) for state in ('pending','failed')}
    return render_template('operations.html',title=section.replace('_',' ').title(),section=section,items=items,jobs=jobs,redis_configured=bool(current_app.config['REDIS_URL']))
