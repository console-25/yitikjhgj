import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import pytest
from noryx import create_app
from noryx.models import *
from noryx.security import hasher

@pytest.fixture
def app(tmp_path):
    app=create_app({'TESTING':True,'SECRET_KEY':'test-secret-key-only','SQLALCHEMY_DATABASE_URI':'sqlite:///'+str(tmp_path/'test.db'),'RATELIMIT_ENABLED':False,'WTF_CSRF_ENABLED':True})
    with app.app_context():
        db.create_all()
        for i,role in enumerate(['client','client','admin','support','billing'],1):
            db.session.add(User(id=i,email=f'{role}{i}@noryx.test',name=role,password_hash=hasher.hash('Testing-only-password7'),role=role))
        category=Category(id=1,name='Test Hosting',slug='test');db.session.add(category);db.session.flush()
        plan=Plan(id=1,category_id=1,name='Verified test plan',status='published',stock=10,specifications={'RAM':'2 GB'})
        db.session.add(plan); db.session.flush();db.session.add(PlanPrice(id=1,plan_id=1,cycle='monthly',currency='INR',amount=9500,setup_fee=500));db.session.commit()
    yield app
    with app.app_context(): db.session.remove(); db.drop_all()

@pytest.fixture
def client(app): return app.test_client()
