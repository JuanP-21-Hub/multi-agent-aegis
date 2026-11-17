import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'app'))
import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session
from server import create_app, User, Account, Event

@pytest.fixture
def bank(tmp_path):
    app=create_app('sqlite:///'+str(tmp_path/'test.db'),mode='fixed')
    app.config['TESTING']=True
    return app

def login(c,user='customer1'):
    r=c.post('/api/login',json={'username':user,'password':'DemoBank!2026'},headers={'X-A2D-Request':'1'})
    assert r.status_code==200
    return {'X-A2D-Request':'1','X-CSRF-Token':r.json['csrf']}

def test_register_ignores_role_and_hashes_password(bank):
    c=bank.test_client();p='A-Strong-Test!'
    r=c.post('/api/register',json=dict(username='newuser',name='테스트',email='new@example.test',password=p,role='staff'),headers={'X-A2D-Request':'1'})
    assert r.status_code==201
    with Session(bank.engine) as db:
        u=db.scalar(select(User).where(User.username=='newuser'))
        assert u.role=='customer' and u.password!=p

def test_login_and_staff_boundary(bank):
    c=bank.test_client()
    assert c.get('/api/customers/2').status_code==401
    login(c)
    assert c.get('/api/customers').status_code==403
    assert c.get('/api/staff').status_code==403
    assert c.get('/api/events').status_code==403
    assert c.get('/api/customers/2').status_code==200
    assert c.get('/api/customers/3').status_code==403

def test_bola_switch_only_affects_customer_detail(bank):
    c=bank.test_client();login(c)
    assert c.get('/api/customers/3').status_code==403
    bank.config['LAB_MODE']='vulnerable'
    r=c.get('/api/customers/3')
    assert r.status_code==200 and r.json['customer']['username']=='customer2'
    assert 'password' not in r.json['customer'] and 'pin' not in r.json['accounts'][0]
    assert c.get('/api/staff').status_code==403
    assert bank.test_client().get('/api/customers/3').status_code==401

def test_accounts_and_pin(bank):
    c=bank.test_client();h=login(c)
    r=c.post('/api/accounts',json={'pin':'6789'},headers=h)
    assert r.status_code==201 and r.json['account']['balance']==0
    aid=r.json['account']['id']
    assert c.post(f'/api/accounts/{aid}/verify-pin',json={'pin':'6789'},headers=h).status_code==200
    assert c.post(f'/api/accounts/{aid}/verify-pin',json={'pin':'0000'},headers=h).status_code==403
    with Session(bank.engine) as db: assert db.get(Account,aid).pin!='6789'
    assert c.post('/api/accounts',json={'pin':'xx'},headers=h).status_code==400
    assert c.post('/api/accounts/2/verify-pin',json={'pin':'1234'},headers=h).status_code==403

def test_csrf_and_origin(bank):
    c=bank.test_client();h=login(c)
    assert c.post('/api/accounts',json={'pin':'1234'}).status_code==403
    assert c.post('/api/accounts',json={'pin':'1234'},headers={**h,'Origin':'https://evil.example'}).status_code==403

def test_staff_management_and_session_revocation(bank):
    c=bank.test_client();h=login(c,'staff')
    assert len(c.get('/api/customers').json['customers'])==2
    r=c.post('/api/staff',json=dict(username='staff2',name='직원2',email='staff2@example.test',password='DemoBank!2026'),headers=h)
    assert r.status_code==201
    uid=r.json['staff']['id'];other=bank.test_client();login(other,'staff2')
    assert c.patch(f'/api/staff/{uid}',json={'active':False},headers=h).status_code==200
    assert other.get('/api/staff').status_code==401
    assert c.patch('/api/staff/1',json={'active':False},headers=h).status_code==400

def test_audit_no_secrets(bank):
    c=bank.test_client();h=login(c);c.get('/api/customers/3')
    with Session(bank.engine) as db:
        event=db.scalar(select(Event).where(Event.path=='/api/customers/3'))
        assert event.status==403 and event.actor_id==2 and event.target_id==3
        assert 'password' not in Event.__table__.columns
    c.post('/api/logout',json={},headers=h)
    assert c.get('/api/accounts').status_code==401

def test_login_rate_limit(bank):
    c=bank.test_client()
    for _ in range(8):assert c.post('/api/login',json={'username':'customer1','password':'bad'},headers={'X-A2D-Request':'1'}).status_code==401
    assert c.post('/api/login',json={'username':'customer1','password':'bad'},headers={'X-A2D-Request':'1'}).status_code==429
