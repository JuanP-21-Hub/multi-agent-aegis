"""Nginx -> FastAPI -> PostgreSQL smoke and restart persistence (isolated test DB)."""
import json
import pathlib
import secrets
import sys
import urllib.request

base = 'http://127.0.0.1:8081'
state_file = pathlib.Path('test-results/smoke-state.json')

def api(path, body=None, token=None):
    headers = {'Content-Type': 'application/json'}
    if token:
        headers['Authorization'] = 'Bearer ' + token
    request = urllib.request.Request(base + '/api' + path, data=json.dumps(body).encode() if body else None, headers=headers)
    with urllib.request.urlopen(request, timeout=15) as response:
        assert response.headers['X-Audit-Persisted'] == 'true'
        return json.load(response)

if sys.argv[1] == 'before':
    with urllib.request.urlopen(base) as r:
        assert 'A2D은행' in r.read().decode()
        assert "script-src 'self'" in r.headers['Content-Security-Policy']
    with urllib.request.urlopen(base+'/static/api.js') as r:
        assert 'Authorization' in r.read().decode()
    state = {'login_id': 'smoke_'+secrets.token_hex(6), 'password': secrets.token_urlsafe(24)}
    api('/customers/signup', {**state, 'full_name': '재시작검증', 'rrn': 'TEST-RRN-654321'})
    token = api('/auth/customer/login', state)['access_token']
    state['customer_id'] = api('/customers/me', token=token)['customer_id']
    state['account'] = api('/accounts', {'account_pin': '9428'}, token)
    api('/accounts/'+str(state['account']['account_id'])+'/verify-pin', {'account_pin': '9428'}, token)
    state_file.parent.mkdir(exist_ok=True)
    state_file.write_text(json.dumps(state))
    print('PASS: Nginx same-origin signup/login/me/account/PIN flow')
else:
    state = json.loads(state_file.read_text())
    token = api('/auth/customer/login', {k:state[k] for k in ('login_id','password')})['access_token']
    assert api('/customers/me', token=token)['customer_id'] == state['customer_id']
    assert state['account'] in api('/accounts/me', token=token)
    print('PASS: customer and account preserved after database/backend/web restart')
