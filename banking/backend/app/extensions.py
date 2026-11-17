"""A2D features on the existing FinLab schema; no Flask or parallel user DB."""
import ipaddress
import json
import logging
import os
import time
import uuid

import jwt
import psycopg
from fastapi import Depends, HTTPException, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, Field, StrictBool, field_validator
from psycopg.rows import dict_row
from starlette.concurrency import run_in_threadpool

from app import main as core

LAB_MODE = os.getenv('LAB_MODE', 'fixed')
if LAB_MODE not in ('fixed', 'vulnerable'):
    raise ValueError('LAB_MODE must be fixed or vulnerable')


class StaffCreate(BaseModel):
    employee_id: str = Field(min_length=4, max_length=50, pattern=r'^[a-zA-Z0-9_]+$')
    display_name: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=12, max_length=128)

    @field_validator('display_name')
    @classmethod
    def clean_name(cls, value):
        if not value.strip():
            raise ValueError('이름을 입력하세요.')
        return value.strip()


class StaffUpdate(BaseModel):
    active: StrictBool


def current_actor(request: Request, credentials=Depends(core.bearer_scheme)):
    if credentials is None:
        raise core.authentication_error()
    try:
        payload = jwt.decode(credentials.credentials, os.environ['JWT_SECRET'],
                             algorithms=['HS256'], issuer='finlab', audience='finlab-client',
                             options={'require': ['sub', 'exp', 'iss', 'aud']})
    except jwt.InvalidTokenError:
        raise core.authentication_error()
    if payload.get('role') == 'CUSTOMER':
        return core.get_current_customer(request, credentials)
    if payload.get('role') in ('STAFF', 'ADMIN'):
        return core.get_current_staff(request, credentials)
    raise core.authentication_error()


def persist_audit(record):
    with core.get_db() as conn, conn.cursor() as cur:
        cur.execute('''INSERT INTO audit_logs
            (actor_type, actor_id, action, target_type, target_id, request_path,
             ip_address, status, request_id, http_method, http_status, duration_ms)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)''', record)


def install(app):
    @app.exception_handler(RequestValidationError)
    async def validation_error(request, exc):
        # Pydantic's default response echoes input, including passwords and RRN.
        labels = {'login_id': '고객 아이디', 'employee_id': '직원 아이디',
                  'password': '비밀번호', 'rrn': '가상 주민번호 (TEST-RRN-숫자 6자리)',
                  'account_pin': '계좌 비밀번호 (숫자 4자리)', 'full_name': '이름',
                  'display_name': '직원 이름', 'active': '활성 상태'}
        errors = [{'loc': list(e['loc']), 'msg': labels.get(str(e['loc'][-1]), '입력값') +
                   ' 형식 또는 길이를 확인해 주세요.', 'type': e['type']} for e in exc.errors()]
        return JSONResponse(status_code=422, content={'detail': errors})

    @app.exception_handler(psycopg.Error)
    async def db_error(request, exc):
        return JSONResponse(status_code=503, content={'detail': '데이터베이스 요청을 처리하지 못했습니다.'})

    @app.middleware('http')
    async def audit(request: Request, call_next):
        if not request.url.path.startswith('/api/'):
            return await call_next(request)
        started = time.perf_counter()
        rid = str(uuid.uuid4())  # Never trust a client-supplied identifier.
        try:
            response = await call_next(request)
        except Exception:
            # Do not print exception locals, request bodies, headers or SQL parameters.
            logging.error('Unhandled API error request_id=%s', rid)
            response = JSONResponse(status_code=500, content={'detail': '서버 오류가 발생했습니다.'})
        if not hasattr(request.state, 'actor_id'):
            # A valid customer denied at a staff endpoint is still an identifiable actor.
            # Revalidate against the DB; never trust unsigned claims for audit identity.
            scheme, _, token = request.headers.get('Authorization', '').partition(' ')
            if scheme.lower() == 'bearer' and token:
                try:
                    credentials = core.HTTPAuthorizationCredentials(scheme='Bearer', credentials=token)
                    await run_in_threadpool(current_actor, request, credentials)
                except (HTTPException, psycopg.Error):
                    pass
        route = request.scope.get('route')
        # Route templates prevent arbitrary secrets in a path/query entering the log.
        path = getattr(route, 'path', '/api/unmatched')
        target_type, target_id = None, None
        for param, kind in [('customer_id', 'CUSTOMER'), ('staff_id', 'STAFF'), ('account_id', 'ACCOUNT')]:
            raw = request.path_params.get(param)
            if isinstance(raw, int) and 0 < raw <= 9223372036854775807:
                target_type, target_id = kind, raw
                break
        try:
            ip = str(ipaddress.ip_address(request.client.host)) if request.client else None
        except ValueError:
            ip = None
        record = (getattr(request.state, 'actor_type', 'GUEST'),
                  getattr(request.state, 'actor_id', None), 'API_REQUEST', target_type,
                  target_id, path, ip, 'SUCCESS' if response.status_code < 400 else 'FAILURE',
                  rid, request.method[:10], response.status_code,
                  min(round((time.perf_counter() - started) * 1000), 2147483647))
        try:
            await run_in_threadpool(persist_audit, record)
            response.headers['X-Audit-Persisted'] = 'true'
        except Exception:
            logging.error('Audit persistence failed request_id=%s', rid)
            response.headers['X-Audit-Persisted'] = 'false'
        response.headers['X-Request-ID'] = rid
        response.headers['Cache-Control'] = 'no-store'
        return response

    @app.get('/api/staff/me')
    def staff_me(staff: dict = Depends(core.get_current_staff)):
        return staff

    @app.post('/api/auth/logout')
    def logout(actor: dict = Depends(current_actor)):
        # Revoke this user's issued JWTs, including tokens in other browser tabs.
        is_customer = 'customer_id' in actor
        table = 'customers' if is_customer else 'staff_users'
        uid = actor['customer_id'] if is_customer else actor['staff_id']
        with core.get_db() as conn, conn.cursor() as cur:
            cur.execute(f'UPDATE {table} SET token_version = token_version + 1 WHERE id = %s', (uid,))
        return {'message': '로그아웃했습니다.'}

    @app.post('/api/accounts/{account_id}/verify-pin')
    def verify_pin(account_id: int, body: core.CreateAccountRequest,
                   customer: dict = Depends(core.get_current_customer)):
        with core.get_db() as conn, conn.cursor() as cur:
            cur.execute('SELECT account_pin_hash FROM accounts WHERE id = %s AND customer_id = %s',
                        (account_id, customer['customer_id']))
            row = cur.fetchone()
        if not row:
            raise HTTPException(403, '계좌에 접근할 수 없습니다.')
        try:
            core.password_hasher.verify(row[0], body.account_pin)
        except (core.VerificationError, core.InvalidHashError):
            raise HTTPException(403, '계좌 비밀번호가 일치하지 않습니다.')
        return {'verified': True, 'message': '계좌 비밀번호가 확인되었습니다.'}

    @app.get('/api/staff/users')
    def staff_list(after_id: int = Query(0, ge=0), limit: int = Query(100, ge=1, le=500),
                   staff: dict = Depends(core.get_current_staff)):
        with core.get_db() as conn, conn.cursor(row_factory=dict_row) as cur:
            cur.execute('''SELECT id AS staff_id, employee_id, display_name, role, active
                           FROM staff_users WHERE id > %s ORDER BY id LIMIT %s''', (after_id, limit))
            return cur.fetchall()

    @app.post('/api/staff/users', status_code=201)
    def staff_create(body: StaffCreate, staff: dict = Depends(core.get_current_staff)):
        try:
            with core.get_db() as conn, conn.cursor(row_factory=dict_row) as cur:
                cur.execute('''INSERT INTO staff_users (employee_id, display_name, password_hash, role)
                               VALUES (%s,%s,%s,'STAFF')
                               RETURNING id AS staff_id, employee_id, display_name, role, active''',
                            (body.employee_id, body.display_name, core.password_hasher.hash(body.password)))
                return cur.fetchone()
        except psycopg.errors.UniqueViolation:
            raise HTTPException(409, '이미 사용 중인 직원 아이디입니다.')

    @app.patch('/api/staff/users/{staff_id}')
    def staff_update(staff_id: int, body: StaffUpdate, staff: dict = Depends(core.get_current_staff)):
        if staff_id == staff['staff_id']:
            raise HTTPException(400, '본인 계정의 활성 상태는 변경할 수 없습니다.')
        with core.get_db() as conn, conn.cursor(row_factory=dict_row) as cur:
            cur.execute('''UPDATE staff_users SET active = %s,
                           token_version = token_version + CASE WHEN active IS DISTINCT FROM %s THEN 1 ELSE 0 END
                           WHERE id = %s
                           RETURNING id AS staff_id, employee_id, display_name, role, active''',
                        (body.active, body.active, staff_id))
            row = cur.fetchone()
        if not row:
            raise HTTPException(404, '직원을 찾을 수 없습니다.')
        return row

    @app.get('/api/customers/{customer_id}', response_model=core.CustomerMeResponse)
    def lab_customer_detail(customer_id: int, customer: dict = Depends(core.get_current_customer)):
        # The only intentionally vulnerable authorization check in the application.
        if LAB_MODE == 'fixed' and customer_id != customer['customer_id']:
            raise HTTPException(403, '다른 고객의 정보는 조회할 수 없습니다.')
        with core.get_db() as conn, conn.cursor(row_factory=dict_row) as cur:
            cur.execute('SELECT id AS customer_id, login_id, full_name FROM customers WHERE id = %s', (customer_id,))
            row = cur.fetchone()
        if not row:
            raise HTTPException(404, '고객을 찾을 수 없습니다.')
        # Deliberately limited to non-secret profile fields; PIN/account routes stay protected.
        return row

    @app.get('/api/lab')
    def lab(staff: dict = Depends(core.get_current_staff)):
        return {'mode': LAB_MODE, 'endpoint': '/api/customers/{customer_id}', 'scenario': '고객 상세 BOLA'}

    @app.get('/api/staff/audit-logs')
    def audit_logs(format: str = Query('json', pattern='^(json|jsonl)$'),
                   before_id: int | None = Query(None, gt=0), limit: int = Query(200, ge=1, le=1000),
                   staff: dict = Depends(core.get_current_staff)):
        with core.get_db() as conn, conn.cursor(row_factory=dict_row) as cur:
            # Explicit allowlist: historical details/IP/arbitrary paths are never exported.
            cur.execute('''SELECT id, created_at, actor_type, actor_id, target_type, target_id,
                           request_id, request_path, http_method, http_status, status, duration_ms
                           FROM audit_logs WHERE (%s::bigint IS NULL OR id < %s)
                           ORDER BY id DESC LIMIT %s''', (before_id, before_id, limit))
            items = cur.fetchall()
        known_paths = {r.path for r in app.routes}
        for item in items:
            if item['request_path'] not in known_paths:
                item['request_path'] = '/api/legacy-or-unmatched'
            item['created_at'] = item['created_at'].isoformat() if item['created_at'] else None
            item['request_id'] = str(item['request_id']) if item['request_id'] else None
        if format == 'jsonl':
            return Response(''.join(json.dumps(i, ensure_ascii=False) + '\n' for i in items),
                            media_type='application/x-ndjson',
                            headers={'Content-Disposition': 'attachment; filename=a2d-audit.jsonl'})
        return {'items': items, 'next_before_id': items[-1]['id'] if len(items) == limit else None}
