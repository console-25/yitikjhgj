import re
from datetime import timedelta
import pytest
from noryx.models import *
from noryx.security import digest, hasher

PASSWORD='Testing-only-password7'
def csrf(client,path='/login'):
    response=client.get(path)
    match=re.search(r'name="csrf_token" value="([^"]+)"',response.get_data(as_text=True))
    assert match,response.status_code
    return match.group(1)
def post(client,url,data=None,source='/login'):
    return client.post(url,data={**(data or {}),'csrf_token':csrf(client,source)})
def login(client,email='client1@noryx.test'):
    return post(client,'/login',{'email':email,'password':PASSWORD})
def order(client,key='unique-order'):
    return post(client,'/checkout/1',{'checkout_key':key,'total':'1','amount':'1'},'/checkout/1')

def test_roles_and_logout(client,app):
    assert client.get('/client/dashboard').status_code==302
    assert client.get('/admin/dashboard').status_code==302
    assert login(client).location=='/client/dashboard'
    assert client.get('/admin/dashboard').status_code==403
    with client.session_transaction() as s: old_cookie=dict(s)
    assert post(client,'/logout',source='/client/account').status_code==302
    with client.session_transaction() as s: s.update(old_cookie)
    assert client.get('/client/dashboard').status_code==302
    assert login(client,'admin3@noryx.test').location=='/admin/dashboard'

@pytest.mark.parametrize('url',['/checkout/1','/client/tickets','/client/account','/logout','/admin/users','/admin/catalog','/admin/wallets'])
def test_csrf_required(client,url):
    login(client,'admin3@noryx.test');assert client.post(url,data={}).status_code==400

def test_suspended_and_generic_login(app,client):
    with app.app_context(): db.session.get(User,1).suspended=True;db.session.commit()
    assert login(client).status_code==400
    a=post(client,'/login',{'email':'missing@noryx.test','password':PASSWORD})
    assert b'Unable to sign in with those credentials.' in a.data

def test_price_tampering_duplicate_stock_history(app,client):
    login(client);assert order(client).status_code==302;assert order(client).status_code==302
    with app.app_context():
        assert db.session.scalar(db.select(func.count()).select_from(Order))==1
        o=db.session.scalar(db.select(Order));assert o.total==10000
        assert db.session.get(Plan,1).stock==9
        db.session.get(PlanPrice,1).amount=99999;db.session.get(Plan,1).name='New name';db.session.commit()
        assert o.snapshot['name']=='Verified test plan';assert o.total==10000

from sqlalchemy import func

def test_idor(app,client):
    login(client);order(client)
    post(client,'/client/tickets',{'subject':'Private','department':'Billing','body':'Secret ticket'},'/client/tickets')
    post(client,'/logout',source='/client/account');login(client,'client2@noryx.test')
    for path in ['/client/orders/1','/client/invoices/1','/client/invoices/1/pdf','/tickets/1']:
        assert client.get(path).status_code==404,path

@pytest.mark.parametrize('role,email,allowed,blocked',[
 ('support','support4@noryx.test','/admin/tickets','/admin/orders'),
 ('billing','billing5@noryx.test','/admin/orders','/admin/catalog')])
def test_staff_permissions(client,role,email,allowed,blocked):
    login(client,email);assert client.get(allowed).status_code==200;assert client.get(blocked).status_code==403

def test_unpaid_cannot_fulfill_payment_idempotency(app,client):
    login(client);order(client);post(client,'/logout',source='/client/account');login(client,'admin3@noryx.test')
    data={'reference':'real-service','current_password':PASSWORD}
    assert post(client,'/admin/orders/1/fulfill',data).status_code==409
    payment={'reference':'bank-verified-1','current_password':PASSWORD}
    assert post(client,'/admin/invoices/1/payment',payment).status_code==302
    assert post(client,'/admin/invoices/1/payment',payment).status_code==409
    assert post(client,'/admin/orders/1/fulfill',data).status_code==302
    assert post(client,'/admin/orders/1/fulfill',data).status_code==409
    with app.app_context():
        assert db.session.scalar(db.select(func.count()).select_from(Service))==1
        assert db.session.scalar(db.select(func.count()).select_from(Payment))==1

def test_cancel_restores_stock_once(app,client):
    login(client);order(client)
    assert post(client,'/client/orders/1',source='/client/account').status_code==302
    assert post(client,'/client/orders/1',source='/client/account').status_code==409
    with app.app_context(): assert db.session.get(Plan,1).stock==10

def test_coupon_limits(app,client):
    with app.app_context():
        db.session.add(Coupon(code='SAVE',percent=20,expires_at=now()+timedelta(days=1),max_uses=1));db.session.commit()
    login(client)
    assert post(client,'/checkout/1',{'checkout_key':'coupon1','coupon':'SAVE'},'/checkout/1').status_code==302
    assert post(client,'/checkout/1',{'checkout_key':'coupon2','coupon':'SAVE'},'/checkout/1').status_code==400
    with app.app_context():
        assert db.session.scalar(db.select(Order)).total==8100
        assert db.session.get(Plan,1).stock==9

def test_internal_notes_hidden(client):
    login(client);post(client,'/client/tickets',{'subject':'Help','department':'Billing','body':'Customer text'},'/client/tickets')
    post(client,'/logout',source='/client/account');login(client,'support4@noryx.test')
    assert post(client,'/tickets/1',{'body':'STAFF_ONLY_SECRET','internal':'on'},'/tickets/1').status_code==302
    post(client,'/logout',source='/client/account');login(client)
    assert b'STAFF_ONLY_SECRET' not in client.get('/tickets/1').data

def test_reset_expiry_reuse_revokes(app,client):
    login(client)
    with app.app_context():
        db.session.add(PasswordReset(token_hash=digest('reset-token'),user_id=1,expires_at=now()+timedelta(minutes=5)));db.session.commit()
    assert post(client,'/reset-password',{'token':'reset-token','password':'A-new-testing-password8'}).status_code==302
    assert client.get('/client/dashboard').status_code==302
    assert post(client,'/reset-password',{'token':'reset-token','password':'A-new-testing-password9'}).status_code==400
    with app.app_context():
        db.session.add(PasswordReset(token_hash=digest('expired'),user_id=1,expires_at=now()-timedelta(seconds=1)));db.session.commit()
    assert post(client,'/reset-password',{'token':'expired','password':PASSWORD}).status_code==400

def test_last_admin_and_reauth(client):
    login(client,'admin3@noryx.test')
    assert post(client,'/admin/users',{'user_id':'3','action':'update','role':'client','name':'Admin','current_password':PASSWORD}).status_code==403
    assert post(client,'/admin/users',{'user_id':'1','action':'revoke','current_password':'wrong'}).status_code==403

def test_last_super_admin_protected(app,client):
    with app.app_context():
        db.session.add(User(id=6,email='owner@noryx.test',name='Owner',role='super_admin',password_hash=hasher.hash(PASSWORD)));db.session.commit()
    login(client,'owner@noryx.test')
    assert client.get('/admin/users/6?tab=security').status_code==200
    response=post(client,'/admin/users/6',{'action':'role','role':'admin','current_password':PASSWORD},'/admin/users/6?tab=security')
    assert response.status_code==409

def test_user_management_persist_notes_suspend_and_audit(app,client):
    with app.app_context():
        db.session.add(User(id=6,email='owner@noryx.test',name='Owner',role='super_admin',password_hash=hasher.hash(PASSWORD)));db.session.commit()
    login(client,'owner@noryx.test')
    page=client.get('/admin/users');assert b'User management' in page.data and b'Active users' in page.data
    assert b'client1@noryx.test' in page.data
    detail=client.get('/admin/users/1');assert detail.status_code==200 and b'Overview' in detail.data
    response=post(client,'/admin/users/1',{'action':'profile','first_name':'Updated','last_name':'Customer','username':'updated_user','email':'client1@noryx.test','phone':'1234567890','country':'India','billing_address':'Mumbai','current_password':PASSWORD},'/admin/users/1')
    assert response.status_code==302
    with app.app_context():
        user=db.session.get(User,1);assert (user.name,user.phone,user.country)==('Updated Customer','1234567890','India')
        assert db.session.scalar(db.select(func.count()).select_from(Audit).where(Audit.event=='admin.user_profile_updated'))==1
    note=post(client,'/admin/users/1',{'action':'note','note':'Private review note','current_password':PASSWORD},'/admin/users/1')
    assert note.status_code==302 and b'Private review note' in client.get('/admin/users/1?tab=profile').data
    suspend=post(client,'/admin/users/1',{'action':'suspend','suspended':'on','current_password':PASSWORD},'/admin/users/1')
    assert suspend.status_code==302
    with app.app_context(): assert db.session.get(User,1).suspended
    assert post(client,'/logout',source='/client/account').status_code==302
    assert login(client,'client1@noryx.test').status_code==400

def test_create_user_invitation_and_filters(app,client):
    with app.app_context():
        db.session.add(User(id=6,email='owner@noryx.test',name='Owner',role='super_admin',password_hash=hasher.hash(PASSWORD)));db.session.commit()
    login(client,'owner@noryx.test')
    result=post(client,'/admin/users/new',{'first_name':'Invitee','last_name':'User','username':'invitee01','email':'invitee@example.test','role':'client','current_password':PASSWORD},'/admin/users/new')
    assert result.status_code==302
    with app.app_context():
        user=db.session.scalar(db.select(User).where(User.email=='invitee@example.test'))
        assert user and user.role=='client' and user.email_verified is False
        job=db.session.scalar(db.select(EmailJob).where(EmailJob.recipient==user.email))
        assert job and 'reset-password?token=' in job.body
    assert b'invitee@example.test' in client.get('/admin/users?q=invitee').data

def test_bulk_revoke_sessions(client,app):
    login(client,'admin3@noryx.test')
    response=post(client,'/admin/users',{'action':'bulk_revoke','user_ids':['1','2'],'current_password':PASSWORD})
    assert response.status_code==302
    with app.app_context(): assert db.session.scalar(db.select(func.count()).select_from(LoginSession).where(LoginSession.user_id.in_([1,2])))==0

def test_wallet_no_client_credit_and_no_duplicate(client,app):
    login(client)
    assert post(client,'/admin/wallets',{'user_id':1,'amount':100}).status_code==403
    post(client,'/logout',source='/client/account');login(client,'billing5@noryx.test')
    data={'user_id':1,'amount':1000,'reference':'credit-1','reason':'Verified credit','current_password':PASSWORD}
    assert post(client,'/admin/wallets',data).status_code==302
    assert post(client,'/admin/wallets',data).status_code==409
    data.update(amount=-2000,reference='debit-1')
    assert post(client,'/admin/wallets',data).status_code==409

def test_catalog_edit_sync(client,app):
    login(client,'admin3@noryx.test')
    assert post(client,'/admin/plans/1',{'name':'Updated','category_id':1,'status':'published','stock':4,'specifications':'{"RAM":"4 GB"}','cycle':'monthly','amount':12345,'setup_fee':0,'currency':'INR'}).status_code==302
    assert b'Updated' in client.get('/catalog').data
    assert client.get('/api/catalog').json['plans'][0]['prices'][0]['amount_minor']==12345

def test_xss_escaped_and_pdf(client):
    login(client)
    post(client,'/client/tickets',{'subject':'<script>alert(1)</script>','department':'Billing','body':'<img src=x onerror=alert(1)>'},'/client/tickets')
    data=client.get('/tickets/1').data;assert b'<img src=x' not in data;assert b'&lt;img' in data
    order(client);response=client.get('/client/invoices/1/pdf');assert response.data.startswith(b'%PDF')

def test_uploads_not_accepted(client):
    # This release deliberately exposes no upload handler or public upload directory.
    login(client)
    assert client.post('/tickets/1/attachments',data={'file':'executable'}).status_code in (400,405)

def test_full_page_routes(client):
    login(client,'admin3@noryx.test')
    paths=['/client/dashboard','/catalog','/checkout/1','/client/services','/client/orders','/client/invoices','/client/wallet','/client/tickets','/client/account','/knowledgebase','/admin/dashboard','/admin/users','/admin/catalog','/admin/plans/new','/admin/plans/1','/admin/orders','/admin/wallets','/admin/services','/admin/tickets','/admin/content','/admin/coupons','/admin/audit','/admin/integrations']
    for path in paths: assert client.get(path).status_code==200,path

def test_seed_reset_remove(app):
    runner=app.test_cli_runner()
    assert runner.invoke(args=['seed-demo']).exit_code==0
    assert runner.invoke(args=['seed-demo']).exit_code==0
    with app.app_context(): assert db.session.scalar(db.select(func.count()).select_from(User).where(User.demo.is_(True)))==2
    assert runner.invoke(args=['reset-demo-credentials']).exit_code==0
    assert runner.invoke(args=['remove-demo','--yes']).exit_code==0
    with app.app_context(): assert db.session.scalar(db.select(func.count()).select_from(User).where(User.demo.is_(True)))==0

def test_rate_limit(app):
    from noryx import create_app
    limited=create_app({'TESTING':True,'SECRET_KEY':'test-limit','SQLALCHEMY_DATABASE_URI':app.config['SQLALCHEMY_DATABASE_URI'],'RATELIMIT_ENABLED':True})
    c=limited.test_client()
    statuses=[post(c,'/login',{'email':'absent@test.invalid','password':'wrong'}).status_code for _ in range(11)]
    assert statuses[-1]==429

def test_registration_never_accepts_role(client,app):
    response=post(client,'/register',{'email':'new@example.test','name':'New','password':PASSWORD,'role':'admin'})
    assert response.location=='/client/dashboard'
    with app.app_context(): assert db.session.scalar(db.select(User).where(User.email=='new@example.test')).role=='client'

def test_review_and_empty_stock_cannot_order(client,app):
    login(client)
    with app.app_context(): db.session.get(Plan,1).stock=0; db.session.commit()
    assert post(client,'/checkout/1',{'checkout_key':'no-stock'}).status_code==409
    with app.app_context(): db.session.get(Plan,1).stock=10;db.session.get(Plan,1).status='review';db.session.commit()
    assert post(client,'/checkout/1',{'checkout_key':'review'}).status_code==409

def test_production_configuration_rejected():
    from noryx import create_app
    with pytest.raises(RuntimeError,match='PostgreSQL'):
        create_app({'ENVIRONMENT':'production','SECRET_KEY':'x'*40,'SQLALCHEMY_DATABASE_URI':'sqlite:///:memory:'})

def test_suspension_revokes_live_access(app,client):
    login(client)
    with app.app_context(): db.session.get(User,1).suspended=True;db.session.commit()
    assert client.get('/client/dashboard').status_code==302

def test_reset_requests_generic_and_only_hash_in_reset_table(client,app):
    a=post(client,'/forgot-password',{'email':'client1@noryx.test'})
    b=post(client,'/forgot-password',{'email':'missing@noryx.test'})
    assert a.status_code==b.status_code==302 and a.location==b.location
    with app.app_context():
        reset=db.session.scalar(db.select(PasswordReset));job=db.session.scalar(db.select(EmailJob))
        raw=job.body.split('token=')[1]
        assert reset.token_hash==digest(raw) and raw!=reset.token_hash

def test_email_worker_mock_smtp(app,monkeypatch):
    import noryx, smtplib
    from noryx.jobs import send_email
    sent=[]
    class SMTP:
        def __init__(self,*a,**kw): pass
        def __enter__(self): return self
        def __exit__(self,*a): pass
        def starttls(self,**kw): pass
        def send_message(self,message): sent.append(message)
    monkeypatch.setattr(noryx,'create_app',lambda:app)
    monkeypatch.setattr(smtplib,'SMTP',SMTP)
    monkeypatch.setenv('SMTP_HOST','smtp.example.test');monkeypatch.setenv('SMTP_FROM','support@example.test');monkeypatch.delenv('SMTP_USER',raising=False)
    with app.app_context():
        job=EmailJob(recipient='client1@noryx.test',subject='Test',body='Test message');db.session.add(job);db.session.commit();ident=job.id
    send_email(ident);send_email(ident)
    assert len(sent)==1
    with app.app_context(): assert db.session.get(EmailJob,ident).state=='sent'
