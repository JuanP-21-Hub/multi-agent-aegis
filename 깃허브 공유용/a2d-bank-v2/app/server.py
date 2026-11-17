import os, re, secrets, hashlib, time, json, uuid
from datetime import datetime, timezone
from functools import wraps
from flask import Flask, request, jsonify, g, send_from_directory
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import create_engine, Column, Integer, String, Boolean, ForeignKey, Text, select, func
from sqlalchemy.orm import DeclarativeBase, Session
from sqlalchemy.exc import IntegrityError

class Base(DeclarativeBase): pass
class User(Base):
    __tablename__='users'
    id=Column(Integer,primary_key=True)
    username=Column(String(32),unique=True,nullable=False)
    name=Column(String(40),nullable=False)
    email=Column(String(120),nullable=False)
    password=Column(Text,nullable=False)
    role=Column(String(12),nullable=False,default='customer')
    active=Column(Boolean,nullable=False,default=True)
class Account(Base):
    __tablename__='accounts'
    id=Column(Integer,primary_key=True)
    owner_id=Column(Integer,ForeignKey('users.id'),nullable=False)
    number=Column(String(30),unique=True,nullable=False)
    label=Column(String(50),nullable=False)
    pin=Column(Text,nullable=False)
    balance=Column(Integer,nullable=False,default=0)
    created=Column(String(40),nullable=False)
class LoginSession(Base):
    __tablename__='sessions'
    token=Column(String(64),primary_key=True)
    user_id=Column(Integer,ForeignKey('users.id'),nullable=False)
    csrf=Column(String(64),nullable=False)
    expires=Column(Integer,nullable=False)
class Event(Base):
    __tablename__='events'
    id=Column(Integer,primary_key=True)
    request_id=Column(String(40),nullable=False)
    at=Column(String(40),nullable=False)
    actor_id=Column(Integer)
    role=Column(String(12))
    method=Column(String(10),nullable=False)
    path=Column(String(200),nullable=False)
    target_id=Column(Integer)
    status=Column(Integer,nullable=False)
    duration_ms=Column(Integer,nullable=False)
class Attempt(Base):
    __tablename__='attempts'
    key=Column(String(80),primary_key=True)
    count=Column(Integer,nullable=False,default=0)
    until=Column(Integer,nullable=False)

def now(): return datetime.now(timezone.utc).isoformat()
def digest(s): return hashlib.sha256(s.encode()).hexdigest()
def public_user(u): return dict(id=u.id,username=u.username,name=u.name,email=u.email,role=u.role,active=u.active)
def public_account(a): return dict(id=a.id,number=a.number,label=a.label,balance=a.balance,created=a.created)

def create_app(database_url=None, mode=None, seed=True):
    app=Flask(__name__,static_folder='static')
    app.config.update(MAX_CONTENT_LENGTH=16384)
    app.config['LAB_MODE']=mode or os.getenv('LAB_MODE','fixed')
    if app.config['LAB_MODE'] not in ('fixed','vulnerable'): raise ValueError('LAB_MODE must be fixed or vulnerable')
    url=database_url or os.getenv('DATABASE_URL','sqlite:///a2d-local.db')
    engine=create_engine(url,**({'connect_args':{'check_same_thread':False}} if url.startswith('sqlite') else {}))
    Base.metadata.create_all(engine)
    app.engine=engine
    if seed:
        with Session(engine) as db:
            if not db.scalar(select(User.id).limit(1)):
                for username,name,role in [('staff','운영 직원','staff'),('customer1','김하늘','customer'),('customer2','이서준','customer')]:
                    u=User(username=username,name=name,email=f'{username}@example.test',role=role,password=generate_password_hash(os.getenv('DEMO_PASSWORD','DemoBank!2026')))
                    db.add(u); db.flush()
                    if role=='customer':
                        db.add(Account(owner_id=u.id,number=f'900-2026-{u.id:06d}',label='A2D 데일리 통장',pin=generate_password_hash('1234'),balance=1250000 if username=='customer1' else 2840000,created=now()))
                db.commit()

    def error(message,status=400): return jsonify(error=message),status
    def data(): return request.get_json(silent=True) or {}
    def valid_user(d):
        return (isinstance(d,dict) and all(isinstance(d.get(k),str) for k in ('username','name','email','password')) and re.fullmatch(r'[a-zA-Z0-9_]{4,24}',d['username']) and 1<=len(d['name'].strip())<=40 and re.fullmatch(r'[^\s@]{1,64}@[^\s@]{1,50}\.[^\s@]{2,20}',d['email']) and 10<=len(d['password'])<=128)
    def auth(staff=False):
        def decorator(fn):
            @wraps(fn)
            def wrapped(*a,**kw):
                if not g.user:return error('로그인이 필요합니다.',401)
                if staff and g.user.role!='staff':return error('직원 전용 기능입니다.',403)
                return fn(*a,**kw)
            return wrapped
        return decorator

    @app.before_request
    def before():
        g.started=time.perf_counter();g.request_id=str(uuid.uuid4());g.target=None;g.user=None;g.session=None
        g.db=Session(engine)
        token=request.cookies.get('a2d_session','')
        if token:
            s=g.db.get(LoginSession,digest(token))
            if s and s.expires>time.time():
                u=g.db.get(User,s.user_id)
                if u and u.active:g.user=u;g.session=s
        if request.path.startswith('/api/') and request.method in ('POST','PATCH','DELETE'):
            # Browser cross-origin requests and form posts cannot satisfy this header.
            if request.headers.get('X-A2D-Request')!='1':return error('요청 검증에 실패했습니다.',403)
            origin=request.headers.get('Origin')
            if origin and origin!=request.host_url.rstrip('/'):return error('다른 사이트의 요청은 허용하지 않습니다.',403)
            if g.session and not secrets.compare_digest(request.headers.get('X-CSRF-Token',''),g.session.csrf):return error('세션 검증에 실패했습니다. 새로고침해 주세요.',403)

    @app.after_request
    def after(response):
        response.headers['X-Content-Type-Options']='nosniff'
        response.headers['X-Frame-Options']='DENY'
        response.headers['Referrer-Policy']='same-origin'
        response.headers['Content-Security-Policy']="default-src 'self'; style-src 'self'; script-src 'self'; img-src 'self' data:; frame-ancestors 'none'; base-uri 'self'; form-action 'self'"
        if request.path.startswith('/api/'):
            response.headers['Cache-Control']='no-store'
            response.headers['X-Request-ID']=g.request_id
            try:
                g.db.rollback()
                g.db.add(Event(request_id=g.request_id,at=now(),actor_id=g.user.id if g.user else None,role=g.user.role if g.user else None,method=request.method,path=request.path[:200],target_id=g.target,status=response.status_code,duration_ms=round((time.perf_counter()-g.started)*1000)))
                g.db.commit()
            except Exception:
                g.db.rollback();app.logger.exception('Audit persistence failed')
        return response
    @app.teardown_request
    def teardown(exc):
        if hasattr(g,'db'):g.db.close()
    @app.errorhandler(IntegrityError)
    def conflict(exc):
        g.db.rollback();return error('이미 사용 중인 값입니다. 다른 값으로 시도해 주세요.',409)
    @app.errorhandler(413)
    def too_big(exc):return error('입력 내용이 너무 큽니다.',413)
    @app.get('/')
    def index():return send_from_directory(app.static_folder,'index.html')
    @app.get('/api/health')
    def health():
        g.db.execute(select(1));return jsonify(status='ok')
    @app.get('/api/me')
    def me():return jsonify(user=public_user(g.user) if g.user else None,csrf=g.session.csrf if g.session else None)
    @app.post('/api/register')
    def register():
        d=data()
        if not valid_user(d):return error('아이디 4~24자(영문·숫자·_), 비밀번호 10~128자와 올바른 이름·이메일을 입력해 주세요.')
        u=User(username=d['username'],name=d['name'].strip(),email=d['email'],password=generate_password_hash(d['password']),role='customer')
        g.db.add(u);g.db.commit();g.target=u.id
        return jsonify(message='회원가입이 완료되었습니다. 로그인해 주세요.'),201
    @app.post('/api/login')
    def login():
        d=data()
        if not isinstance(d,dict):return error('잘못된 입력입니다.')
        username=d.get('username','');password=d.get('password','')
        if not isinstance(username,str) or not isinstance(password,str) or len(username)>32 or len(password)>128:return error('입력값을 확인해 주세요.')
        key=digest((request.remote_addr or '')+':'+username)
        a=g.db.get(Attempt,key);t=int(time.time())
        if a and a.until>t and a.count>=8:return error('로그인 시도가 많습니다. 5분 후 다시 시도해 주세요.',429)
        u=g.db.scalar(select(User).where(User.username==username))
        if not u or not u.active or not check_password_hash(u.password,password):
            if not a:a=Attempt(key=key,count=0,until=t+300);g.db.add(a)
            if a.until<=t:a.count=0;a.until=t+300
            a.count+=1;g.db.commit();return error('아이디 또는 비밀번호를 확인해 주세요.',401)
        if a:g.db.delete(a)
        if g.session:g.db.delete(g.session)
        token=secrets.token_urlsafe(32);s=LoginSession(token=digest(token),user_id=u.id,csrf=secrets.token_hex(24),expires=t+7200)
        g.db.add(s);g.db.commit();g.user=u;g.session=s
        r=jsonify(user=public_user(u),csrf=s.csrf)
        r.set_cookie('a2d_session',token,httponly=True,samesite='Strict',max_age=7200,secure=os.getenv('COOKIE_SECURE')=='1')
        return r
    @app.post('/api/logout')
    @auth()
    def logout():
        g.db.delete(g.session);g.db.commit()
        r=jsonify(message='로그아웃했습니다.');r.delete_cookie('a2d_session');return r
    @app.get('/api/accounts')
    @auth()
    def accounts():return jsonify(accounts=[public_account(a) for a in g.db.scalars(select(Account).where(Account.owner_id==g.user.id).order_by(Account.id))])
    @app.post('/api/accounts')
    @auth()
    def open_account():
        if g.user.role!='customer':return error('고객 계정에서 계좌를 발급해 주세요.',403)
        d=data();pin=d.get('pin','') if isinstance(d,dict) else ''
        if not isinstance(pin,str) or not re.fullmatch(r'\d{4}',pin,flags=re.ASCII):return error('계좌 비밀번호는 숫자 4자리입니다.')
        if g.db.scalar(select(func.count()).select_from(Account).where(Account.owner_id==g.user.id))>=5:return error('실습 계좌는 최대 5개까지 발급할 수 있습니다.')
        a=Account(owner_id=g.user.id,number='900-'+str(secrets.randbelow(10**12)).zfill(12),label='A2D 데일리 통장',pin=generate_password_hash(pin),balance=0,created=now())
        g.db.add(a);g.db.commit();g.target=g.user.id
        return jsonify(account=public_account(a)),201
    @app.post('/api/accounts/<int:aid>/verify-pin')
    @auth()
    def verify_pin(aid):
        a=g.db.get(Account,aid)
        if not a or a.owner_id!=g.user.id:return error('계좌에 접근할 수 없습니다.',403)
        d=data();pin=d.get('pin','') if isinstance(d,dict) else ''
        if not isinstance(pin,str) or len(pin)!=4:return error('계좌 비밀번호를 확인해 주세요.')
        key=f'pin:{g.user.id}:{aid}';at=g.db.get(Attempt,key);t=int(time.time())
        if at and at.until>t and at.count>=5:return error('5분 후 다시 시도해 주세요.',429)
        if not check_password_hash(a.pin,pin):
            if not at:at=Attempt(key=key,count=0,until=t+300);g.db.add(at)
            if at.until<=t:at.count=0;at.until=t+300
            at.count+=1;g.db.commit();return error('계좌 비밀번호가 일치하지 않습니다.',403)
        if at:g.db.delete(at);g.db.commit()
        return jsonify(message='계좌 비밀번호가 확인되었습니다.')
    @app.get('/api/customers')
    @auth(staff=True)
    def customers():
        users=g.db.scalars(select(User).where(User.role=='customer').order_by(User.id)).all()
        return jsonify(customers=[public_user(u) for u in users])
    @app.get('/api/customers/<int:uid>')
    @auth()
    def customer(uid):
        g.target=uid
        # INTENTIONAL LAB BOLA: this is the ONLY mode-dependent authorization check.
        if app.config['LAB_MODE']=='fixed' and g.user.role!='staff' and g.user.id!=uid:return error('다른 고객의 정보는 조회할 수 없습니다.',403)
        u=g.db.get(User,uid)
        if not u or u.role!='customer':return error('고객을 찾을 수 없습니다.',404)
        return jsonify(customer=public_user(u),accounts=[public_account(a) for a in g.db.scalars(select(Account).where(Account.owner_id==uid))])
    @app.get('/api/staff')
    @auth(staff=True)
    def staff():return jsonify(staff=[public_user(u) for u in g.db.scalars(select(User).where(User.role=='staff').order_by(User.id))])
    @app.post('/api/staff')
    @auth(staff=True)
    def add_staff():
        d=data()
        if not valid_user(d):return error('아이디·이름·이메일과 10자 이상의 비밀번호를 확인해 주세요.')
        u=User(username=d['username'],name=d['name'].strip(),email=d['email'],password=generate_password_hash(d['password']),role='staff')
        g.db.add(u);g.db.commit();g.target=u.id;return jsonify(staff=public_user(u)),201
    @app.patch('/api/staff/<int:uid>')
    @auth(staff=True)
    def update_staff(uid):
        u=g.db.get(User,uid);d=data();g.target=uid
        if not u or u.role!='staff':return error('직원 계정을 찾을 수 없습니다.',404)
        if not isinstance(d,dict) or type(d.get('active')) is not bool:return error('활성 상태를 지정해 주세요.')
        if uid==g.user.id:return error('현재 로그인한 본인 계정은 비활성화할 수 없습니다.')
        u.active=d['active']
        if not u.active:
            for s in g.db.scalars(select(LoginSession).where(LoginSession.user_id==uid)):g.db.delete(s)
        g.db.commit();return jsonify(staff=public_user(u))
    @app.get('/api/lab')
    @auth(staff=True)
    def lab():return jsonify(mode=app.config['LAB_MODE'],scenario='고객 상세 조회 BOLA',endpoint='/api/customers/{id}')
    @app.get('/api/events')
    @auth(staff=True)
    def events():
        rows=g.db.scalars(select(Event).order_by(Event.id.desc()).limit(200)).all()
        items=[{c.name:getattr(e,c.name) for c in Event.__table__.columns} for e in rows]
        if request.args.get('format')=='jsonl':return app.response_class('\n'.join(json.dumps(i,ensure_ascii=False) for i in reversed(items))+'\n',mimetype='application/x-ndjson',headers={'Content-Disposition':'attachment; filename=a2d-events.jsonl'})
        return jsonify(events=items)
    return app

if __name__=='__main__':
    create_app().run(host=os.getenv('BIND_HOST','127.0.0.1'),port=int(os.getenv('PORT','8081')),debug=False)
