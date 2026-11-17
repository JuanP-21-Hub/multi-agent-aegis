'use strict';
// Every API call, including JSONL downloads, goes through this same-origin client.
const BankAPI=(()=>{
  const KEY='a2d.jwt.v1';
  let auth=null, expiryTimer;
  function clearAuth(notify=false){
    auth=null;clearTimeout(expiryTimer);
    sessionStorage.removeItem(KEY);localStorage.removeItem(KEY);
    if(notify)window.dispatchEvent(new Event('bank:auth-lost'));
  }
  function schedule(){clearTimeout(expiryTimer);if(auth)expiryTimer=setTimeout(()=>clearAuth(true),Math.max(0,auth.expiresAt-Date.now()))}
  function restore(){
    try{auth=JSON.parse(sessionStorage.getItem(KEY)||localStorage.getItem(KEY)||'null')}
    catch{clearAuth()}
    if(auth&&(!auth.token||!['customer','staff'].includes(auth.kind)||!Number.isFinite(auth.expiresAt)||auth.expiresAt<=Date.now()))clearAuth();
    schedule();
  }
  restore();
  window.addEventListener('storage',e=>{if(e.key===KEY){auth=null;restore();window.dispatchEvent(new Event('bank:auth-lost'))}});
  function setAuth(result,kind,remember){
    clearAuth();
    auth={token:result.access_token,kind,expiresAt:Date.now()+result.expires_in*1000};
    (remember?localStorage:sessionStorage).setItem(KEY,JSON.stringify(auth));schedule();
  }
  async function request(path,method='GET',body,download=false){
    if(!path.startsWith('/')||path.startsWith('//'))throw new Error('잘못된 API 경로입니다.');
    if(auth&&auth.expiresAt<=Date.now())clearAuth(true);
    const sentToken=auth?.token;
    const headers={Accept:download?'application/x-ndjson':'application/json'};
    if(body!==undefined)headers['Content-Type']='application/json';
    if(sentToken)headers.Authorization='Bearer '+sentToken;
    const controller=new AbortController(),timer=setTimeout(()=>controller.abort(),15000);
    try{
      const response=await fetch('/api'+path,{method,headers,credentials:'omit',cache:'no-store',
        body:body===undefined?undefined:JSON.stringify(body),signal:controller.signal});
      if(!response.ok){
        let data;try{data=await response.json()}catch{data={}}
        if(response.status===401&&!path.endsWith('/login')&&sentToken===auth?.token)clearAuth(true);
        let message=Array.isArray(data.detail)?data.detail.map(e=>e.msg).join(' / '):data.detail;
        if(message==='Database operation failed'||message==='Database connection failed')message='데이터베이스 연결을 확인해 주세요.';
        const error=new Error(typeof message==='string'?message:'요청을 처리하지 못했습니다. 잠시 후 다시 시도해 주세요.');
        error.status=response.status;throw error;
      }
      if(sentToken&&sentToken!==auth?.token)throw new Error('로그인 상태가 변경되었습니다. 다시 요청해 주세요.');
      if(response.headers.get('X-Audit-Persisted')==='false')window.dispatchEvent(new Event('bank:audit-failed'));
      return download?await response.blob():await response.json();
    }catch(error){
      if(error.name==='AbortError')throw new Error('응답 시간이 초과되었습니다. 다시 시도해 주세요.');
      if(error instanceof TypeError)throw new Error('서버에 연결하지 못했습니다. 연결 상태를 확인해 주세요.');
      throw error;
    }finally{clearTimeout(timer)}
  }
  return {request,setAuth,clearAuth,getAuth:()=>auth};
})();
