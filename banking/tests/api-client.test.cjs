const {test}=require('node:test');
const assert=require('node:assert/strict');
const vm=require('node:vm');
const fs=require('node:fs');
const path=require('node:path');
function client(initial,fetchImpl){
  const storage=()=>{const m=new Map();return {getItem:k=>m.get(k)||null,setItem:(k,v)=>m.set(k,v),removeItem:k=>m.delete(k)}};
  const sessionStorage=storage(),localStorage=storage(),events=[];
  if(initial)localStorage.setItem('a2d.jwt.v1',JSON.stringify(initial));
  const ctx={sessionStorage,localStorage,Date,JSON,Number,Error,TypeError,AbortController,Event,
    setTimeout:()=>1,clearTimeout:()=>{},window:{addEventListener:()=>{},dispatchEvent:e=>events.push(e.type)},fetch:fetchImpl};
  vm.createContext(ctx);vm.runInContext(fs.readFileSync(path.join(__dirname,'../frontend/api.js'),'utf8')+'\nthis.api=BankAPI;',ctx);
  ctx.events=events;return ctx;
}
const response=(status,body)=>new Response(JSON.stringify(body),{status,headers:{'content-type':'application/json'}});
test('JWT sent as Bearer, same origin, no session cookies',async()=>{
  let call;const c=client(null,async(...args)=>(call=args,response(200,{})));
  c.api.setAuth({access_token:'test-token',expires_in:3600},'customer',false);
  await c.api.request('/accounts','POST',{account_pin:'1234'});
  assert.equal(call[0],'/api/accounts');assert.equal(call[1].headers.Authorization,'Bearer test-token');
  assert.equal(call[1].credentials,'omit');assert.equal(JSON.parse(call[1].body).account_pin,'1234');
  assert.ok(c.sessionStorage.getItem('a2d.jwt.v1'));assert.equal(c.localStorage.getItem('a2d.jwt.v1'),null);
});
test('remember login restores on reload and expired storage is removed',()=>{
  const c=client({token:'saved',kind:'staff',expiresAt:Date.now()+60000},()=>{});
  assert.equal(c.api.getAuth().kind,'staff');
  const expired=client({token:'expired',kind:'customer',expiresAt:1},()=>{});
  assert.equal(expired.api.getAuth(),null);assert.equal(expired.localStorage.getItem('a2d.jwt.v1'),null);
});
test('401 clears login; 403 leaves authenticated customer logged in',async()=>{
  const c=client(null,async()=>response(403,{detail:'직원 전용 기능입니다.'}));
  c.api.setAuth({access_token:'test',expires_in:3600},'customer',true);
  await assert.rejects(c.api.request('/staff/me'),{message:'직원 전용 기능입니다.'});assert.ok(c.api.getAuth());
  c.fetch=async()=>response(401,{detail:'만료'});
  await assert.rejects(c.api.request('/customers/me'));
  assert.equal(c.api.getAuth(),null);assert.ok(c.events.includes('bank:auth-lost'));
});
test('validation errors and authenticated JSONL download',async()=>{
  const c=client(null,async()=>response(422,{detail:[{msg:'가상 주민번호 형식을 확인해 주세요.'}]}));
  await assert.rejects(c.api.request('/customers/signup','POST',{}),{message:'가상 주민번호 형식을 확인해 주세요.'});
  let authorization;c.fetch=async(url,opts)=>{authorization=opts.headers.Authorization;return new Response('{"id":1}\n')};
  c.api.setAuth({access_token:'download-token',expires_in:3600},'staff',true);
  const blob=await c.api.request('/staff/audit-logs?format=jsonl','GET',undefined,true);
  assert.equal(authorization,'Bearer download-token');assert.equal(await blob.text(),'{"id":1}\n');
  c.api.clearAuth();assert.equal(c.api.getAuth(),null);assert.equal(c.localStorage.getItem('a2d.jwt.v1'),null);
});
