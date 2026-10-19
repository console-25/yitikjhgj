from datetime import timedelta
from noryx.models import *
from test_platform import login, post, order, PASSWORD

def test_workspace_routes_permissions(client):
    login(client,'admin3@noryx.test')
    paths=['analytics','settings','addons','locations','processors','stock','invoices','transactions','refunds','infrastructure','provisioning','monitoring','health','staff','media','catalog?view=categories','catalog?view=locations','catalog?view=processors','content?kind=article']
    for path in paths: assert client.get('/admin/'+path).status_code==200,path
    login(client)
    for path in paths[:15]: assert client.get('/admin/'+path).status_code==403,path

def test_settings_reauthentication_and_registration(app,client):
    login(client,'admin3@noryx.test')
    assert post(client,'/admin/settings?tab=security',{'current_password':PASSWORD}).status_code==403
    with app.app_context(): db.session.get(User,3).role='super_admin';db.session.commit()
    assert post(client,'/admin/settings?tab=security',{'current_password':'incorrect'}).status_code==403
    assert post(client,'/admin/settings?tab=security',{'current_password':PASSWORD}).status_code==302
    assert client.get('/register').status_code==403
    values=dict(current_password=PASSWORD,site_name='Noryx Hosting',public_url='https://example.test',timezone='Asia/Kolkata',currency='USD')
    assert post(client,'/admin/settings',values).status_code==302
    assert post(client,'/admin/settings',{**values,'public_url':'javascript:alert(1)'}).status_code==400
    with app.app_context(): assert db.session.get(WorkspaceSetting,'currency').value=='USD'

def test_ticket_assignment_authorization(app,client):
    login(client)
    assert post(client,'/client/tickets',dict(subject='Help',department='Billing',body='Question')).status_code==302
    values=dict(action='manage',priority='urgent',status='awaiting_staff',assigned_id='4')
    assert post(client,'/tickets/1',values).status_code==403
    login(client,'support4@noryx.test')
    assert post(client,'/tickets/1',values).status_code==302
    assert post(client,'/tickets/1',{**values,'assigned_id':'1'}).status_code==400
    with app.app_context():
        ticket=db.session.get(Ticket,1);assert ticket.priority=='urgent';assert ticket.assigned_id==4

def test_archived_and_future_announcements(app,client):
    with app.app_context():
        db.session.add_all([Announcement(title='Public notice',body='Public',publish_at=now()),Announcement(title='Archived secret',body='Archive',archived=True),Announcement(title='Future secret',body='Scheduled',publish_at=now()+timedelta(days=1))]);db.session.commit()
    login(client)
    for path in ['/client/announcements','/client/dashboard']:
        page=client.get(path).data;assert b'Public notice' in page;assert b'Archived secret' not in page;assert b'Future secret' not in page

def test_currency_metrics_and_order_rejection(app,client):
    login(client);order(client,'first');order(client,'second');order(client,'third')
    with app.app_context():
        db.session.add_all([Payment(invoice_id=1,reference='INR-1',amount=10000,currency='INR',actor_id=3),Payment(invoice_id=2,reference='USD-1',amount=5000,currency='USD',actor_id=3)]);db.session.commit()
        from noryx.workspace import dashboard_metrics
        with app.test_request_context('/admin/analytics?currency=USD'):
            metrics=dashboard_metrics();assert metrics['total_revenue']==5000;assert sum(metrics['values'])==5000
    login(client,'admin3@noryx.test')
    assert client.get('/admin/order/3').status_code==200
    assert post(client,'/admin/orders/3/cancel',{'current_password':PASSWORD}).status_code==302
    assert post(client,'/admin/orders/3/cancel',{'current_password':PASSWORD}).status_code==409
    with app.app_context(): assert db.session.get(Plan,1).stock==8

def test_orders_pagination_and_search(app,client):
    with app.app_context():
        for i in range(31): db.session.add(Order(user_id=1,plan_id=1,idempotency_key=f'page-{i}',snapshot={'name':'Batch plan','cycle':'monthly'},total=100,currency='INR',status='paid' if i%2 else 'awaiting_payment'))
        db.session.commit()
    login(client,'admin3@noryx.test')
    assert client.get('/admin/orders').data.count(b'data-order-drawer')==25
    assert client.get('/admin/orders?page=2').data.count(b'data-order-drawer')==6
    assert client.get('/admin/orders?status=paid').data.count(b'data-order-drawer')==15
    assert client.get('/admin/orders?q=%2331').data.count(b'data-order-drawer')==1

def test_self_and_last_superadmin_protected(app,client):
    with app.app_context(): db.session.get(User,3).role='super_admin';db.session.commit()
    login(client,'admin3@noryx.test')
    response=post(client,'/admin/users/3',dict(action='profile',email='admin3@noryx.test',first_name='Console',last_name='',suspended='on',current_password=PASSWORD))
    assert response.status_code==409
    with app.app_context(): assert not db.session.get(User,3).suspended

def test_addon_and_plan_presentation_persist(app,client):
    login(client,'admin3@noryx.test')
    assert post(client,'/admin/addons',dict(name='Backup',description='Definition only',amount=100,currency='INR',active='on')).status_code==302
    values=dict(name='Featured plan',category_id=1,status='published',stock=10,specifications='{"RAM":"4 GB"}',currency='INR',cycle='monthly',amount=9500,setup_fee=0,display_order=2,featured='on')
    assert post(client,'/admin/plans/1',values).status_code==302
    with app.app_context():
        plan=db.session.get(Plan,1);assert plan.featured;assert plan.display_order==2
        assert db.session.scalar(db.select(ProductRevision)).snapshot['edited_by']==3
