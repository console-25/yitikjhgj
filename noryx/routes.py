import io
import re
import secrets
from datetime import timedelta, datetime
from pathlib import Path
from flask import Blueprint, abort, current_app, flash, g, redirect, render_template, request, send_file, send_from_directory, session, url_for, jsonify
from sqlalchemy import func, or_
from .models import *
from .security import *
from .business import place_order, record_manual_payment, fulfill, cancel_order, CYCLES, snapshot

web=Blueprint('web',__name__)
DEPARTMENTS=('General Support','Technical Support','Billing','Sales','Abuse Reports')

def textfield(name,maximum=200,optional=False):
    value=request.form.get(name,'').strip()
    if (not optional and not value) or len(value)>maximum: abort(400,f'Invalid {name.replace("_"," ")}.')
    return value

def integer(name,minimum=0,maximum=10**9):
    try: value=int(request.form.get(name,''))
    except ValueError: abort(400,f'Invalid {name}.')
    if not minimum<=value<=maximum: abort(400,f'Invalid {name}.')
    return value

def email_input():
    value=textfield('email',254).lower()
    if not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+',value): abort(400,'Enter a valid email address.')
    return value

def dashboard_url(user): return '/admin/dashboard' if user.role!='client' else '/client/dashboard'
def rows(model,limit=200): return db.session.scalars(db.select(model).order_by(model.id.desc()).limit(limit)).all()

def _public_url():
    from .workspace import preference
    return preference('public_url',current_app.config['PUBLIC_URL'])

def _queue_password_reset(user):
    token=secrets.token_urlsafe(48)
    db.session.execute(db.update(PasswordReset).where(PasswordReset.user_id==user.id).values(used=True))
    db.session.add(PasswordReset(token_hash=digest(token),user_id=user.id,expires_at=now()+timedelta(minutes=30)))
    link=_public_url().rstrip('/')+'/reset-password?token='+token
    db.session.add(EmailJob(recipient=user.email,subject='Set or reset your Noryx Hosting password',body='Use this secure link within 30 minutes: '+link))
    return token

@web.route('/login',methods=['GET','POST'])
@limiter.limit('10 per minute',methods=['POST'])
def login():
    if request.method=='POST':
        email=request.form.get('email','').strip().lower()[:254]
        password=request.form.get('password','')[:129]
        user=db.session.scalar(db.select(User).where(User.email==email))
        valid=verify(user.password_hash if user else DUMMY_HASH,password)
        if not user or not valid or user.suspended:
            audit('auth.login_failed'); db.session.commit()
            return render_template('auth.html',mode='login',title='Welcome back',error='Unable to sign in with those credentials.'),400
        sign_in(user,request.form.get('remember')=='on')
        return redirect(dashboard_url(user))
    return render_template('auth.html',mode='login',title='Welcome back')

@web.route('/register',methods=['GET','POST'])
@limiter.limit('5 per hour',methods=['POST'])
def register():
    from .workspace import preference
    if not preference("registration_open",True): abort(403,"Registration is currently closed.")
    if request.method=='POST':
        email=email_input(); name=textfield('name',100); password=request.form.get('password','')
        if not password_valid(password):
            return render_template('auth.html',mode='register',title='Create your account',error='Use 12–128 characters, including letters and a number.'),400
        if db.session.scalar(db.select(User.id).where(User.email==email)):
            return render_template('auth.html',mode='register',title='Create your account',error='Unable to register. Try signing in or resetting your password.'),400
        user=User(email=email,name=name,password_hash=hasher.hash(password),role='client')
        db.session.add(user)
        try: db.session.commit()
        except Exception:
            db.session.rollback(); abort(409,'Unable to register. Try signing in.')
        sign_in(user); return redirect('/client/dashboard')
    return render_template('auth.html',mode='register',title='Create your account')

@web.route('/forgot-password',methods=['GET','POST'])
@limiter.limit('5 per hour',methods=['POST'])
def forgot():
    if request.method=='POST':
        email=request.form.get('email','').strip().lower()[:254]
        user=db.session.scalar(db.select(User).where(User.email==email,User.suspended.is_(False)))
        if user:
            token=secrets.token_urlsafe(48)
            db.session.execute(db.update(PasswordReset).where(PasswordReset.user_id==user.id).values(used=True))
            db.session.add(PasswordReset(token_hash=digest(token),user_id=user.id,expires_at=now()+timedelta(minutes=30)))
            link=_public_url().rstrip('/')+'/reset-password?token='+token
            db.session.add(EmailJob(recipient=email,subject='Reset your Noryx Hosting password',body='Reset your password within 30 minutes: '+link))
            audit('auth.reset_requested',actor=user.id); db.session.commit()
        flash('If the account is eligible, a reset email has been queued.'); return redirect('/forgot-password')
    return render_template('auth.html',mode='forgot',title='Reset your password')

@web.route('/reset-password',methods=['GET','POST'])
@limiter.limit('10 per hour',methods=['POST'])
def reset():
    token=request.values.get('token','')[:200]
    if request.method=='POST':
        reset=db.session.scalar(db.select(PasswordReset).where(PasswordReset.token_hash==digest(token)).with_for_update())
        if not reset or reset.used or reset.expires_at<=now(): abort(400,'This reset link is invalid or expired.')
        password=request.form.get('password','')
        if not password_valid(password): abort(400,'Use 12–128 characters including letters and a number.')
        changed=db.session.execute(db.update(PasswordReset).where(PasswordReset.id==reset.id,PasswordReset.used.is_(False)).values(used=True))
        if not changed.rowcount: abort(400,'Reset link already used.')
        user=db.session.get(User,reset.user_id)
        user.password_hash=hasher.hash(password); revoke(user.id)
        audit('auth.password_reset',actor=user.id); db.session.commit(); session.clear()
        flash('Password updated. Please sign in.'); return redirect('/login')
    return render_template('auth.html',mode='reset',title='Choose a new password',token=token)

@web.post('/logout')
@required()
def logout():
    db.session.delete(g.login_session); audit('auth.logout'); db.session.commit(); session.clear()
    return redirect('/login')

@web.get('/client/dashboard')
@required()
def client_dashboard():
    uid=g.user.id
    stats={
        'Active services':db.session.scalar(db.select(func.count()).select_from(Service).where(Service.user_id==uid,Service.status=='active')),
        'Pending orders':db.session.scalar(db.select(func.count()).select_from(Order).where(Order.user_id==uid,Order.status.in_(['awaiting_payment','paid']))),
        'Unpaid invoices':db.session.scalar(db.select(func.count()).select_from(Invoice).where(Invoice.user_id==uid,Invoice.status=='unpaid')),
        'Open tickets':db.session.scalar(db.select(func.count()).select_from(Ticket).where(Ticket.user_id==uid,Ticket.status.not_in(['closed','resolved']))),
    }
    return render_template('dashboard.html',title='Your hosting, at a glance',stats=stats,
        announcements=db.session.scalars(db.select(Announcement).where(Announcement.publish_at<=now(),Announcement.archived.is_(False)).order_by(Announcement.pinned.desc(),Announcement.id.desc()).limit(10)).all(),
        active_services=db.session.scalars(db.select(Service).where(Service.user_id==uid,Service.status=='active').order_by(Service.next_due).limit(5)).all(),
        recent_orders=db.session.scalars(db.select(Order).where(Order.user_id==uid).order_by(Order.id.desc()).limit(5)).all(),
        recent_invoices=db.session.scalars(db.select(Invoice).where(Invoice.user_id==uid).order_by(Invoice.id.desc()).limit(5)).all())

@web.get('/catalog')
def catalog():
    query=db.select(Plan).where(Plan.status=='published')
    for field in ('category_id','location_id','processor_id'):
        value=request.args.get(field,type=int)
        if value: query=query.where(getattr(Plan,field)==value)
    return render_template('catalog.html',title='Find your next hosting plan',plans=db.session.scalars(query.order_by(Plan.display_order,Plan.id)).all(),categories=rows(Category),locations=rows(Location),processors=rows(Processor))

@web.get('/api/catalog')
def catalog_api():
    return jsonify(plans=[{'id':p.id,'name':p.name,'category':p.category.name,'stock':p.stock,
        'specifications':p.specifications,'prices':[{'id':v.id,'cycle':v.cycle,'currency':v.currency,'amount_minor':v.amount,'setup_fee_minor':v.setup_fee} for v in p.prices]}
        for p in db.session.scalars(db.select(Plan).where(Plan.status=='published'))])

@web.route('/checkout/<int:price_id>',methods=['GET','POST'])
@required()
@limiter.limit('20 per minute',methods=['POST'])
def checkout(price_id):
    price=db.get_or_404(PlanPrice,price_id)
    if request.method=='POST':
        order=place_order(g.user.id,price_id,request.form.get('checkout_key',''),request.form.get('coupon','').strip()[:40])
        return redirect('/client/orders/'+str(order.id))
    if price.plan.status!='published': abort(404)
    return render_template('checkout.html',title='Review your order',price=price,key=secrets.token_urlsafe(32))

@web.get('/client/orders')
@required()
def orders():
    return render_template('records.html',title='Your orders',kind='orders',records=db.session.scalars(db.select(Order).where(Order.user_id==g.user.id).order_by(Order.id.desc())).all())

@web.route('/client/orders/<int:ident>',methods=['GET','POST'])
@required()
def order_detail(ident):
    order=owned(Order,ident)
    if request.method=='POST': cancel_order(ident,g.user.id); return redirect(request.path)
    invoice=db.session.scalar(db.select(Invoice).where(Invoice.order_id==ident))
    return render_template('order.html',title=f'Order #{ident}',order=order,invoice=invoice)

@web.get('/client/invoices')
@required()
def invoices():
    return render_template('records.html',title='Invoices',kind='invoices',records=db.session.scalars(db.select(Invoice).where(Invoice.user_id==g.user.id).order_by(Invoice.id.desc())).all())

@web.get('/client/invoices/<int:ident>')
@required()
def invoice_detail(ident):
    invoice=owned(Invoice,ident,'billing')
    return render_template('invoice.html',title=invoice.number,invoice=invoice,payment=db.session.scalar(db.select(Payment).where(Payment.invoice_id==ident)))

@web.get('/client/invoices/<int:ident>/pdf')
@required()
def invoice_pdf(ident):
    invoice=owned(Invoice,ident,'billing')
    from reportlab.pdfgen import canvas
    output=io.BytesIO(); pdf=canvas.Canvas(output)
    pdf.setTitle(invoice.number); pdf.setFont('Helvetica-Bold',22); pdf.drawString(50,790,'Noryx Hosting')
    pdf.setFont('Helvetica',12)
    lines=[invoice.number,invoice.created_at.strftime('%Y-%m-%d'),f'Status: {invoice.status}',
        invoice.order.snapshot['name'],f"Cycle: {invoice.order.snapshot['cycle']}",
        f'Total: {invoice.currency} {invoice.total/100:.2f}']
    for i,line in enumerate(lines): pdf.drawString(50,740-i*25,line[:100])
    pdf.save(); output.seek(0)
    return send_file(output,mimetype='application/pdf',as_attachment=True,download_name=invoice.number+'.pdf')

@web.get('/client/services')
@required()
def services():
    return render_template('records.html',title='Your services',kind='services',records=db.session.scalars(db.select(Service).where(Service.user_id==g.user.id)).all())

@web.route('/client/services/<int:ident>',methods=['GET','POST'])
@required()
def service_detail(ident):
    service=owned(Service,ident)
    if request.method=='POST':
        kind=request.form.get('kind')
        if kind not in ('renewal','change_plan','cancellation'): abort(400)
        db.session.add(ServiceRequest(service_id=ident,kind=kind,detail=textfield('detail',4000)))
        audit('service.request',f'{ident}: {kind}'); db.session.commit(); flash('Your request has been recorded for staff review.')
        return redirect(request.path)
    return render_template('service.html',title=service.order.snapshot['name'],service=service)

@web.get('/client/wallet')
@required()
def wallet():
    entries=db.session.scalars(db.select(WalletEntry).where(WalletEntry.user_id==g.user.id).order_by(WalletEntry.id.desc())).all()
    return render_template('wallet.html',title='Wallet ledger',entries=entries,balance=sum(x.amount for x in entries))

@web.route('/client/tickets',methods=['GET','POST'])
@required()
@limiter.limit('20 per hour',methods=['POST'])
def tickets():
    if request.method=='POST':
        department=request.form.get('department')
        if department not in DEPARTMENTS: abort(400)
        subject=textfield('subject',200); body=textfield('body',10000)
        ticket=Ticket(user_id=g.user.id,subject=subject,department=department)
        db.session.add(ticket); db.session.flush()
        db.session.add(TicketReply(ticket_id=ticket.id,user_id=g.user.id,body=body))
        audit('ticket.created',ticket.id); db.session.commit(); return redirect('/tickets/'+str(ticket.id))
    return render_template('tickets.html',title='Support',records=db.session.scalars(db.select(Ticket).where(Ticket.user_id==g.user.id).order_by(Ticket.id.desc())).all(),departments=DEPARTMENTS)

@web.route('/tickets/<int:ident>',methods=['GET','POST'])
@required()
def ticket_detail(ident):
    ticket=owned(Ticket,ident,'support'); staff='support' in PERMISSIONS[g.user.role]
    if request.method=='POST':
        action=request.form.get('action','reply')
        if action=='reply':
            internal=staff and request.form.get('internal')=='on'
            db.session.add(TicketReply(ticket_id=ident,user_id=g.user.id,body=textfield('body',10000),internal=internal))
            if not internal: ticket.status='awaiting_customer' if staff else 'awaiting_staff'
        elif action=='manage':
            if not staff: abort(403)
            priority=request.form.get('priority'); status=request.form.get('status')
            if priority not in ('low','normal','high','urgent') or status not in ('awaiting_staff','awaiting_customer','resolved','closed'): abort(400)
            assigned=request.form.get('assigned_id',type=int)
            if assigned:
                agent=db.get_or_404(User,assigned)
                if agent.suspended or agent.deleted_at or 'support' not in PERMISSIONS.get(agent.role,set()): abort(400,'Choose an active support team member.')
            ticket.priority=priority; ticket.status=status; ticket.assigned_id=assigned
        elif action in ('close','reopen'): ticket.status='closed' if action=='close' else 'awaiting_staff'
        else: abort(400)
        audit('ticket.'+action,ident); db.session.commit(); return redirect(request.path)
    return render_template('ticket.html',title=ticket.subject,ticket=ticket,staff=staff,staff_members=db.session.scalars(db.select(User).where(User.role.in_(['super_admin','admin','support']),User.suspended.is_(False),User.deleted_at.is_(None))).all() if staff else [],replies=[r for r in ticket.replies if staff or not r.internal])

@web.route('/client/account',methods=['GET','POST'])
@required()
@limiter.limit('10 per hour',methods=['POST'])
def account():
    if request.method=='POST':
        action=request.form.get('action')
        if action=='profile':
            g.user.name=textfield('name',100); g.user.billing_address=textfield('billing_address',2000,True)
        elif action=='password':
            reauthenticate(); password=request.form.get('password','')
            if not password_valid(password): abort(400,'Use 12–128 characters including letters and a number.')
            g.user.password_hash=hasher.hash(password); revoke(g.user.id); session.clear()
        elif action=='revoke':
            reauthenticate(); revoke(g.user.id); session.clear()
        else: abort(400)
        audit('account.'+action); db.session.commit(); flash('Account updated.')
        return redirect('/client/account' if action=='profile' else '/login')
    return render_template('account.html',title='Account & security',sessions=db.session.scalars(db.select(LoginSession).where(LoginSession.user_id==g.user.id,LoginSession.expires_at>now())).all())

@web.get('/knowledgebase')
def knowledgebase():
    q=request.args.get('q','')[:100]
    query=db.select(Article).where(Article.published.is_(True))
    if q: query=query.where(or_(Article.title.ilike('%'+q+'%'),Article.body.ilike('%'+q+'%')))
    return render_template('knowledge.html',title='Knowledgebase',articles=db.session.scalars(query).all(),q=q)

@web.get('/admin/dashboard')
@required()
def admin_dashboard():
    from .workspace import dashboard_metrics
    metrics=dashboard_metrics()
    if g.user.role=='client': abort(403)
    stats={'Registered users':db.session.scalar(db.select(func.count()).select_from(User).where(User.deleted_at.is_(None))),
        'Active services':db.session.scalar(db.select(func.count()).select_from(Service).where(Service.status=='active')),
        'Pending orders':db.session.scalar(db.select(func.count()).select_from(Order).where(Order.status.in_(['paid','awaiting_payment']))),
        'Unpaid invoices':db.session.scalar(db.select(func.count()).select_from(Invoice).where(Invoice.status=='unpaid')),
        'Open tickets':db.session.scalar(db.select(func.count()).select_from(Ticket).where(Ticket.status.not_in(['closed','resolved']))),
        'Revenue recorded':metrics['total_revenue']}
    return render_template('dashboard.html',title='Operations overview',stats=stats,announcements=[],**metrics,
        recent_orders=db.session.scalars(db.select(Order).order_by(Order.id.desc()).limit(6)).all(),
        recent_tickets=db.session.scalars(db.select(Ticket).where(Ticket.status.not_in(['closed','resolved'])).order_by(Ticket.id.desc()).limit(5)).all(),
        recent_users=db.session.scalars(db.select(User).where(User.deleted_at.is_(None)).order_by(User.id.desc()).limit(5)).all())

@web.route('/admin/users',methods=['GET','POST'])
@required('users')
def admin_users():
    if request.method=='POST':
        reauthenticate()
        action=request.form.get('action')
        if action in ('bulk_revoke','bulk_suspend'):
            ids=[]
            for value in request.form.getlist('user_ids')[:100]:
                try: ids.append(int(value))
                except ValueError: abort(400,'Invalid selected user.')
            selected=db.session.scalars(db.select(User).where(User.id.in_(set(ids)),User.deleted_at.is_(None))).all()
            if not selected: abort(400,'Select at least one active account.')
            if any(item.role=='super_admin' for item in selected) and g.user.role!='super_admin': abort(403,'Only a Super Admin can manage Super Admin accounts.')
            if action=='bulk_suspend' and any(item.id==g.user.id for item in selected): abort(409,'You cannot suspend your own active administrator account.')
            if action=='bulk_revoke':
                for item in selected: revoke(item.id)
            else:
                for item in selected:
                    _ensure_admin_survives(item,item.role,True)
                    item.suspended=True; revoke(item.id)
            audit('admin.users_bulk_action',f'changed_fields={"sessions" if action=="bulk_revoke" else "status,sessions"}; count={len(selected)}; outcome=success')
            db.session.commit(); flash(f'{len(selected)} account(s) updated.'); return redirect(request.path)
        user=db.get_or_404(User,integer('user_id',1))
        if user.deleted_at: abort(409,'Deleted accounts are read-only.')
        if user.role=='super_admin' and g.user.role!='super_admin': abort(403,'Only a Super Admin can manage a Super Admin account.')
        if action=='revoke': revoke(user.id)
        elif action=='update':
            new_role=request.form.get('role')
            if new_role not in PERMISSIONS: abort(400,'Unknown role.')
            if new_role!=user.role and g.user.role!='super_admin': abort(403,'Only a Super Admin can change roles.')
            new_status=request.form.get('suspended')=='on'
            _ensure_admin_survives(user, new_role, new_status)
            user.name=textfield('name',100); user.suspended=new_status
            if g.user.role=='super_admin': user.role=new_role
            revoke(user.id)
        else: abort(400)
        audit('user.'+action,f'user_id={user.id}; changed_fields=name,role,status,sessions; outcome=success'); db.session.commit(); return redirect(request.path)
    query=db.select(User).where(User.deleted_at.is_(None))
    q=request.args.get('q','')[:100]
    if q: query=query.where(or_(User.email.ilike('%'+q+'%'),User.name.ilike('%'+q+'%'),User.username.ilike('%'+q+'%'),User.first_name.ilike('%'+q+'%'),User.last_name.ilike('%'+q+'%')))
    if request.args.get('role') in PERMISSIONS: query=query.where(User.role==request.args['role'])
    status=request.args.get('status')
    if status=='active': query=query.where(User.suspended.is_(False))
    elif status=='suspended': query=query.where(User.suspended.is_(True))
    sort={'id':User.id,'name':User.name,'email':User.email,'role':User.role,'created':User.created_at,'last_login':User.last_login_at}.get(request.args.get('sort','id'),User.id)
    direction=request.args.get('direction','desc')
    if direction not in ('asc','desc'): direction='desc'
    page=max(1,request.args.get('page',1,type=int)); per_page=25
    total=db.session.scalar(db.select(func.count()).select_from(query.subquery())) or 0
    users=db.session.scalars(query.order_by(sort.asc() if direction=='asc' else sort.desc(),User.id.desc()).offset((page-1)*per_page).limit(per_page)).all()
    total_users=db.session.scalar(db.select(func.count()).select_from(User).where(User.deleted_at.is_(None))) or 0
    active_users=db.session.scalar(db.select(func.count()).select_from(User).where(User.deleted_at.is_(None),User.suspended.is_(False))) or 0
    suspended_users=total_users-active_users
    from calendar import monthrange
    current=now(); month_start=current.replace(day=1,hour=0,minute=0,second=0,microsecond=0)
    new_users=db.session.scalar(db.select(func.count()).select_from(User).where(User.deleted_at.is_(None),User.created_at>=month_start)) or 0
    service_counts=db.session.query(Service.user_id,func.count(Service.id)).filter(Service.status=='active').group_by(Service.user_id).all()
    order_counts=db.session.query(Order.user_id,func.count(Order.id)).group_by(Order.user_id).all()
    services=dict(service_counts); orders=dict(order_counts)
    return render_template('users.html',title='User management',users=users,q=q,roles=PERMISSIONS,page=page,pages=max(1,(total+per_page-1)//per_page),total=total,sort=request.args.get('sort','id'),direction=direction,status=status,stats={'Total users':total_users,'Active users':active_users,'Suspended':suspended_users,'New this month':new_users},services=services,orders=orders)

def _ensure_admin_survives(user,new_role,new_suspended):
    if user.id==g.user.id and (new_suspended or new_role!=user.role): abort(409,'You cannot suspend or demote your own active account.')
    if user.role=='super_admin' and (new_role!='super_admin' or new_suspended):
        remaining=db.session.scalar(db.select(func.count()).select_from(User).where(User.id!=user.id,User.role=='super_admin',User.suspended.is_(False),User.deleted_at.is_(None))) or 0
        if remaining<1: abort(409,'Keep at least one active Super Admin.')
    if user.role in ('admin','super_admin') and not user.suspended and (new_role not in ('admin','super_admin') or new_suspended):
        remaining=db.session.scalar(db.select(func.count()).select_from(User).where(User.id!=user.id,User.role.in_(['admin','super_admin']),User.suspended.is_(False),User.deleted_at.is_(None))) or 0
        if remaining<1: abort(409,'Keep at least one active privileged administrator.')

@web.route('/admin/users/new',methods=['GET','POST'])
@required('users')
@limiter.limit('20 per hour',methods=['POST'])
def admin_user_create():
    if request.method=='POST':
        reauthenticate()
        email=email_input()
        if db.session.scalar(db.select(User.id).where(User.email==email)): abort(409,'That email address is already registered.')
        role=request.form.get('role','client')
        allowed={'client'}|({'admin','support','billing'} if g.user.role=='super_admin' else set())
        if role not in allowed: abort(403,'You cannot grant that role.')
        first=textfield('first_name',60); last=textfield('last_name',60,True)
        username=textfield('username',40,True) or None
        if username and db.session.scalar(db.select(User.id).where(User.username.ilike(username))): abort(409,'Username is already in use.')
        if username and not re.fullmatch(r'[A-Za-z0-9_.-]{3,40}',username): abort(400,'Use 3–40 letters, numbers, dots, dashes or underscores.')
        user=User(email=email,name=(first+' '+last).strip(),first_name=first,last_name=last,username=username,role=role,suspended=request.form.get('suspended')=='on',password_hash=hasher.hash(secrets.token_urlsafe(48)),email_verified=False)
        db.session.add(user); db.session.flush(); _queue_password_reset(user)
        audit('admin.user_created',f'user_id={user.id}; fields=name,email,role,status; outcome=success')
        db.session.commit(); flash('Account created. A secure password setup link is queued for email delivery.')
        return redirect(f'/admin/users/{user.id}')
    return render_template('user_create.html',title='Create user')

@web.route('/admin/users/<int:ident>',methods=['GET','POST'])
@required('users')
@limiter.limit('30 per hour',methods=['POST'])
def admin_user_detail(ident):
    user=db.get_or_404(User,ident)
    if request.method=='POST':
        if user.deleted_at: abort(409,'Deleted accounts are read-only.')
        action=request.form.get('action')
        reauthenticate()
        if user.role=='super_admin' and g.user.role!='super_admin': abort(403,'Only a Super Admin can manage this account.')
        if action=='profile':
            email=email_input()
            conflict=db.session.scalar(db.select(User.id).where(User.email==email,User.id!=user.id))
            if conflict: abort(409,'Email address is already in use.')
            username=textfield('username',40,True) or None
            if username and not re.fullmatch(r'[A-Za-z0-9_.-]{3,40}',username): abort(400,'Use 3–40 letters, numbers, dots, dashes or underscores.')
            if username and db.session.scalar(db.select(User.id).where(User.username.ilike(username),User.id!=user.id)): abort(409,'Username is already in use.')
            old_email=user.email
            user.username=username; user.first_name=textfield('first_name',60); user.last_name=textfield('last_name',60,True)
            user.name=(user.first_name+' '+user.last_name).strip(); user.phone=textfield('phone',32,True); user.country=textfield('country',80,True)
            user.billing_address=textfield('billing_address',2000,True)
            if email!=old_email:
                user.email=email; user.email_verified=False; revoke(user.id)
            new_status=request.form.get('suspended')=='on'; _ensure_admin_survives(user,user.role,new_status); user.suspended=new_status
            if g.user.role=='super_admin':
                asked_verified=request.form.get('email_verified')=='on'
                if asked_verified and email!=old_email: abort(400,'Confirm the new address separately before marking it verified.')
                user.email_verified=asked_verified
            prefs={key:request.form.get('notify_'+key)=='on' for key in ('billing','support','security','announcements')}
            user.notification_preferences=prefs
            fields='username,name,email,phone,country,billing_address,status,notification_preferences'+(',email_verified' if g.user.role=='super_admin' else '')
            audit('admin.user_profile_updated',f'user_id={user.id}; changed_fields={fields}; outcome=success')
        elif action=='role':
            if g.user.role!='super_admin': abort(403,'Only a Super Admin can change account roles.')
            role=request.form.get('role')
            if role not in PERMISSIONS: abort(400,'Unknown role.')
            _ensure_admin_survives(user,role,user.suspended)
            if user.role=='super_admin' and role!='super_admin':
                remaining=db.session.scalar(db.select(func.count()).select_from(User).where(User.id!=user.id,User.role=='super_admin',User.suspended.is_(False),User.deleted_at.is_(None))) or 0
                if remaining<1: abort(409,'Keep at least one active Super Admin.')
            if user.id==g.user.id and role!='super_admin': abort(409,'You cannot demote your own Super Admin account.')
            user.role=role; revoke(user.id)
            audit('admin.user_role_changed',f'user_id={user.id}; changed_fields=role; new_role={role}; outcome=success')
        elif action=='suspend':
            if user.id==g.user.id: abort(409,'You cannot suspend your own active account.')
            suspended=request.form.get('suspended')=='on'
            if suspended and user.id==g.user.id: abort(409,'You cannot suspend your own active account.')
            _ensure_admin_survives(user,user.role,suspended)
            if user.role=='super_admin' and suspended:
                remaining=db.session.scalar(db.select(func.count()).select_from(User).where(User.id!=user.id,User.role=='super_admin',User.suspended.is_(False),User.deleted_at.is_(None))) or 0
                if remaining<1: abort(409,'Keep at least one active Super Admin.')
            user.suspended=suspended
            if suspended: revoke(user.id)
            audit('admin.user_status_changed',f'user_id={user.id}; changed_fields=status,sessions; suspended={suspended}; outcome=success')
        elif action=='revoke':
            revoke(user.id); audit('admin.sessions_revoked',f'user_id={user.id}; outcome=success')
        elif action=='reset':
            _queue_password_reset(user); audit('admin.password_reset_link_queued',f'user_id={user.id}; outcome=success')
            db.session.commit(); flash('A single-use password setup link is queued for delivery.'); return redirect(request.path+'?tab=security')
        elif action=='note':
            note=textfield('note',4000); db.session.add(UserNote(user_id=user.id,actor_id=g.user.id,body=note))
            audit('admin.internal_note_added',f'user_id={user.id}; changed_fields=internal_note; outcome=success')
        elif action=='delete':
            if g.user.role!='super_admin': abort(403,'Only a Super Admin can deactivate and redact an account.')
            if user.role=='super_admin' and user.id==g.user.id: abort(409,'You cannot deactivate your own Super Admin account.')
            _ensure_admin_survives(user,'client',True)
            user.deleted_at=now(); user.suspended=True; user.email=f'deleted+{user.id}@accounts.invalid'; user.username=None
            user.name='Deleted account'; user.first_name='Deleted'; user.last_name='account'; user.phone=''; user.country=''; user.billing_address=''; user.email_verified=False
            user.notification_preferences={}; revoke(user.id)
            audit('admin.user_soft_deleted',f'user_id={user.id}; changed_fields=personal_data,status,sessions; financial_history=retained; outcome=success')
        else: abort(400,'Unknown action.')
        db.session.commit(); flash('Changes saved and recorded in the audit log.')
        return redirect(request.path+'?tab='+request.form.get('tab','overview'))
    services=db.session.scalars(db.select(Service).where(Service.user_id==user.id).order_by(Service.id.desc())).all()
    orders=db.session.scalars(db.select(Order).where(Order.user_id==user.id).order_by(Order.id.desc())).all()
    invoices=db.session.scalars(db.select(Invoice).where(Invoice.user_id==user.id).order_by(Invoice.id.desc())).all()
    wallets=db.session.scalars(db.select(WalletEntry).where(WalletEntry.user_id==user.id).order_by(WalletEntry.id.desc())).all()
    tickets=db.session.scalars(db.select(Ticket).where(Ticket.user_id==user.id).order_by(Ticket.id.desc())).all()
    sessions=db.session.scalars(db.select(LoginSession).where(LoginSession.user_id==user.id,LoginSession.expires_at>now()).order_by(LoginSession.id.desc())).all()
    notes=db.session.scalars(db.select(UserNote).where(UserNote.user_id==user.id).order_by(UserNote.id.desc())).all()
    history=db.session.scalars(db.select(Audit).where(or_(Audit.actor_id==user.id,Audit.detail.like(f'%user_id={user.id};%'))).order_by(Audit.id.desc()).limit(100)).all()
    payments_by_invoice={}
    if invoices:
        for payment in db.session.scalars(db.select(Payment).where(Payment.invoice_id.in_([item.id for item in invoices])).order_by(Payment.created_at.desc())):
            payments_by_invoice.setdefault(payment.invoice_id,[]).append(payment)
    tab=request.args.get('tab','overview')
    if tab not in {'overview','profile','services','orders','invoices','wallet','tickets','sessions','activity','security'}: tab='overview'
    return render_template('user_detail.html',title=f'User #{user.id}',user=user,services=services,orders=orders,invoices=invoices,wallets=wallets,tickets=tickets,sessions=sessions,notes=notes,history=history,tab=tab,payments_by_invoice=payments_by_invoice)

@web.route('/admin/catalog',methods=['GET','POST'])
@required('catalog')
def admin_catalog():
    if request.method=='POST':
        kind=request.form.get('kind')
        if kind=='category':
            slug=textfield('slug',100)
            if not re.fullmatch('[a-z0-9-]+',slug): abort(400,'Use a lowercase URL slug.')
            if db.session.scalar(db.select(Category.id).where(Category.slug==slug)): abort(409,'Category already exists.')
            db.session.add(Category(name=textfield('name',100),slug=slug))
        elif kind in ('location','processor'):
            model=Location if kind=='location' else Processor
            ident=request.form.get('id',type=int)
            item=db.get_or_404(model,ident) if ident else model()
            item.name=textfield('name',100); item.description=textfield('description',2000,True); item.active=request.form.get('active')=='on'
            db.session.add(item)
        else: abort(400)
        audit('catalog.'+kind)
        try: db.session.commit()
        except Exception: db.session.rollback(); abort(409,'A record with this name already exists.')
        return redirect(request.full_path)
    return render_template('admin_catalog.html',title='Hosting catalog',plans=rows(Plan),categories=rows(Category),locations=rows(Location),processors=rows(Processor))

@web.route('/admin/plans/new',methods=['GET','POST'],defaults={'ident':None})
@web.route('/admin/plans/<int:ident>',methods=['GET','POST'])
@required('catalog')
def admin_plan(ident):
    import json
    plan=db.get_or_404(Plan,ident) if ident else Plan()
    if request.method=='POST':
        plan.name=textfield('name',120); plan.description=textfield('description',4000,True)
        plan.category_id=db.get_or_404(Category,integer('category_id',1)).id
        for field,model in [('location_id',Location),('processor_id',Processor)]:
            value=request.form.get(field)
            setattr(plan,field,db.get_or_404(model,integer(field,1)).id if value else None)
        status=request.form.get('status')
        if status not in ('review','published','hidden','archived'): abort(400)
        plan.status=status; plan.stock=integer('stock',0,100000)
        plan.featured=request.form.get('featured')=='on'
        plan.display_order=integer('display_order',0,100000) if 'display_order' in request.form else (plan.display_order or 0)
        try:
            specifications=json.loads(request.form.get('specifications','{}'))
            if not isinstance(specifications,dict) or len(str(specifications))>8000: raise ValueError()
        except (ValueError,TypeError): abort(400,'Specifications must be a JSON object of up to 8,000 characters.')
        plan.specifications=specifications
        currency=textfield('currency',3).upper()
        if currency not in ('INR','USD','EUR','GBP'): abort(400,'Unsupported currency.')
        db.session.add(plan); db.session.flush()
        price=db.session.scalar(db.select(PlanPrice).where(PlanPrice.plan_id==plan.id,PlanPrice.cycle==request.form.get('cycle')))
        cycle=request.form.get('cycle')
        if cycle not in CYCLES: abort(400)
        if not price: price=PlanPrice(plan_id=plan.id,cycle=cycle); db.session.add(price)
        price.amount=integer('amount'); price.setup_fee=integer('setup_fee'); price.currency=currency
        plan.revision=(plan.revision or 0)+1
        db.session.flush(); db.session.expire(plan)
        db.session.add(ProductRevision(plan_id=plan.id,snapshot={**snapshot(plan,price),'edited_by':g.user.id}))
        audit('plan.saved',plan.id); db.session.commit(); flash('Plan saved. Published changes are live in the catalog.')
        return redirect('/admin/catalog')
    revisions=db.session.scalars(db.select(ProductRevision).where(ProductRevision.plan_id==plan.id).order_by(ProductRevision.id.desc()).limit(30)).all() if ident else []
    return render_template('plan.html',title='Edit hosting plan' if ident else 'New hosting plan',plan=plan,categories=rows(Category),locations=rows(Location),processors=rows(Processor),cycles=CYCLES,revisions=revisions,available_plans=rows(Plan))

@web.get('/admin/orders')
@required('billing')
def admin_orders():
    query=db.select(Order).join(User,Order.user_id==User.id)
    q=request.args.get('q','').strip()[:100]; status=request.args.get('status',''); sort=request.args.get('sort','newest')
    if q:
        conditions=[User.name.ilike('%'+q+'%'),User.email.ilike('%'+q+'%'),Order.snapshot['name'].as_string().ilike('%'+q+'%')]
        if q.lstrip('#').isdigit(): conditions.append(Order.id==int(q.lstrip('#')))
        query=query.where(or_(*conditions))
    if status in ('awaiting_payment','paid','active','cancelled'): query=query.where(Order.status==status)
    total=db.session.scalar(db.select(func.count()).select_from(query.subquery()))
    pages=max(1,(total+24)//25); page=max(1,min(request.args.get('page',1,type=int),pages))
    ordering={'newest':Order.id.desc(),'oldest':Order.id.asc(),'amount_high':Order.total.desc(),'amount_low':Order.total.asc()}.get(sort,Order.id.desc())
    orders=db.session.scalars(query.order_by(ordering,Order.id).offset((page-1)*25).limit(25)).all()
    return render_template('admin_orders.html',title='Orders & payment review',orders=orders,total=total,pages=pages,page=page,q=q,status=status,sort=sort)

@web.post('/admin/invoices/<int:ident>/payment')
@required('billing')
@limiter.limit('20 per hour')
def manual_payment(ident):
    reauthenticate(); record_manual_payment(ident,textfield('reference',150),g.user.id)
    flash('Verified manual payment recorded.'); return redirect('/admin/orders')

@web.post('/admin/orders/<int:ident>/fulfill')
@required('catalog')
def manual_fulfill(ident):
    reauthenticate(); fulfill(ident,textfield('reference',200)); flash('Manual fulfillment recorded.'); return redirect('/admin/orders')

@web.route('/admin/wallets',methods=['GET','POST'])
@required('billing')
def admin_wallets():
    if request.method=='POST':
        reauthenticate(); user=db.get_or_404(User,integer('user_id',1))
        amount=integer('amount',-10**8,10**8)
        if not amount: abort(400,'Amount must be nonzero.')
        # All adjustments for a user lock the same row before checking balance.
        db.session.scalar(db.select(User).where(User.id==user.id).with_for_update())
        balance=db.session.scalar(db.select(func.coalesce(func.sum(WalletEntry.amount),0)).where(WalletEntry.user_id==user.id))
        if balance+amount<0: abort(409,'Insufficient ledger balance.')
        entry=WalletEntry(user_id=user.id,amount=amount,reference=textfield('reference',150),reason=textfield('reason',2000),actor_id=g.user.id)
        db.session.add(entry); audit('wallet.adjustment',f'user={user.id}; amount={amount}')
        try: db.session.commit()
        except Exception: db.session.rollback(); abort(409,'Reference already recorded.')
        return redirect(request.path)
    return render_template('admin_wallets.html',title='Wallet adjustments',entries=rows(WalletEntry))

@web.get('/admin/services')
@required('catalog')
def admin_services():
    return render_template('admin_services.html',title='Services & requests',services=rows(Service),requests=rows(ServiceRequest))

@web.get('/admin/tickets')
@required('support')
def admin_tickets():
    query=db.select(Ticket).order_by(Ticket.id.desc())
    if request.args.get('status'): query=query.where(Ticket.status==request.args['status'])
    return render_template('tickets.html',title='Support queue',records=db.session.scalars(query.limit(200)).all(),departments=None)

@web.route('/admin/content',methods=['GET','POST'])
@required('content')
def content():
    if request.method=='POST':
        kind=request.form.get('kind')
        if kind not in ('article','announcement'): abort(400)
        model=Article if kind=='article' else Announcement
        ident=request.form.get('id',type=int); item=db.get_or_404(model,ident) if ident else model()
        item.title=textfield('title',200); item.body=textfield('body',20000)
        if kind=='article': item.category=textfield('category',100); item.published=request.form.get('published')=='on'
        else:
            try: item.publish_at=datetime.fromisoformat(request.form.get('publish_at',''))
            except ValueError: abort(400,'Enter a valid publication date and time in UTC.')
            item.pinned=request.form.get('pinned')=='on'
            item.archived=request.form.get('archived')=='on'
        db.session.add(item); audit('content.'+kind); db.session.commit(); return redirect(request.full_path)
    return render_template('content.html',title='Announcements & knowledgebase',articles=rows(Article),announcements=rows(Announcement),utc_now=now())

@web.route('/admin/coupons',methods=['GET','POST'])
@required('billing')
def coupons():
    if request.method=='POST':
        try: expires=datetime.fromisoformat(request.form.get('expires_at',''))
        except ValueError: abort(400,'Invalid expiration date.')
        category=request.form.get('category_id',type=int)
        if category: db.get_or_404(Category,category)
        db.session.add(Coupon(code=textfield('code',40).upper(),percent=integer('percent',1,100),max_uses=integer('max_uses'),expires_at=expires,category_id=category))
        audit('coupon.created')
        try: db.session.commit()
        except Exception: db.session.rollback(); abort(409,'Coupon already exists.')
        return redirect(request.path)
    return render_template('coupons.html',title='Coupons',coupons=rows(Coupon),categories=rows(Category))

@web.get('/admin/audit')
@required('audit')
def audit_log(): return render_template('audit.html',title='Audit log',events=rows(Audit))

@web.get('/admin/integrations')
@required('audit')
def integrations(): return render_template('integrations.html',title='Integrations')

@web.get('/health/live')
def live(): return {'status':'ok'}

@web.get('/health/ready')
def ready():
    try:
        db.session.execute(db.select(User.id).limit(1))
        if current_app.config['REDIS_URL']:
            from redis import Redis
            Redis.from_url(current_app.config['REDIS_URL'],socket_connect_timeout=2,socket_timeout=2).ping()
    except Exception:
        db.session.rollback(); return {'status':'unavailable'},503
    return {'status':'ready'}

@web.get('/client/')
@web.get('/client')
@web.get('/client/<path:legacy>')
def legacy_client(legacy=''):
    if 'register' in legacy: target='/register'
    elif any(s in legacy for s in ['store','cart','order']): target='/catalog'
    elif any(s in legacy for s in ['ticket','contact']): target='/client/tickets'
    elif 'invoice' in legacy: target='/client/invoices'
    else: target='/login' if not g.user else dashboard_url(g.user)
    return redirect(target,302)

@web.get('/')
@web.get('/<path:filename>')
def public(filename='index.html'):
    root=Path(current_app.config['SITE_ROOT']).resolve()
    candidate=(root/filename).resolve()
    if not candidate.is_relative_to(root) or any(p.startswith('.') for p in Path(filename).parts): abort(404)
    if candidate.is_dir(): filename=filename.rstrip('/')+'/index.html'
    if filename.endswith('.html') and (root/filename).is_file():
        # Route into the maintained catalog without rewriting archived React bundles.
        content=(root/filename).read_text()
        if 'noryx-runtime.js' in content:
            content=content.replace('noryx-runtime.js?v=noryx4','noryx-runtime.js?v=backend5').replace('noryx-runtime.js?v=noryx3','noryx-runtime.js?v=backend5')
        return current_app.response_class(content,mimetype='text/html')
    return send_from_directory(root,filename)
