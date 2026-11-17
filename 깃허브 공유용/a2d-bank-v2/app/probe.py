"""Read-only BOLA comparison against this locally running mock bank."""
import argparse, http.cookiejar, json, urllib.request, urllib.error, urllib.parse
p=argparse.ArgumentParser(description='A2D 로컬 실습 서버 BOLA 비교')
p.add_argument('--url',default='http://127.0.0.1:8081')
p.add_argument('--expect',choices=['fixed','vulnerable'],required=True)
a=p.parse_args();url=a.url.rstrip('/');u=urllib.parse.urlsplit(url)
if u.scheme!='http' or u.hostname not in ('127.0.0.1','localhost') or u.username or u.password or u.query or u.fragment or u.path:
    p.error('이 스크립트는 http://127.0.0.1 또는 http://localhost 실습 서버만 지원합니다.')
opener=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
csrf=''
def call(path,body=None):
    r=urllib.request.Request(url+'/api'+path,data=json.dumps(body).encode() if body is not None else None,headers={'Content-Type':'application/json','X-A2D-Request':'1','X-CSRF-Token':csrf})
    try:
        with opener.open(r,timeout=15) as response:return response.status,json.load(response)
    except urllib.error.HTTPError as e:return e.code,json.load(e)
    except urllib.error.URLError as e:raise SystemExit('서버에 연결하지 못했습니다. docker compose ps에서 backend 상태와 주소를 확인해 주세요.')
status,d=call('/login',{'username':'customer1','password':'DemoBank!2026'})
if status!=200:raise SystemExit('기본 customer1 로그인 실패: '+str(d))
csrf=d['csrf'];own=d['user']['id']
# These are seeded mock account IDs, not discovered external targets.
normal,own_data=call('/customers/'+str(own))
attack,other=call('/customers/3')
expected=403 if a.expect=='fixed' else 200
success=normal==200 and attack==expected and (a.expect=='fixed' or other.get('customer',{}).get('username')=='customer2')
print(json.dumps({'scenario':'customer1 → customer2 상세 조회','normal_status':normal,'other_customer_status':attack,'expected_status':expected,'verified':success},ensure_ascii=False,indent=2))
call('/logout',{})
raise SystemExit(0 if success else 1)
