'use strict';
const $=s=>document.querySelector(s), state={user:null,kind:null,view:'overview'}, modal=$('#modal');
const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const won=n=>Number(n).toLocaleString('ko-KR')+' 원';
const role=r=>r==='staff'?'직원 · 관리자':'개인 고객';
let toastTimer;
function toast(s){$('#toast').textContent=s;$('#toast').classList.add('show');clearTimeout(toastTimer);toastTimer=setTimeout(()=>$('#toast').classList.remove('show'),3500)}
const api=(path,method='GET',body)=>BankAPI.request(path,method,body);
const customer=u=>({id:u.customer_id,name:u.full_name,username:u.login_id,role:'customer',rrn_last4:u.rrn_last4});
const staffUser=u=>({id:u.staff_id,name:u.display_name,username:u.employee_id,role:'staff',authority:u.role,active:u.active});
const account=a=>({id:a.account_id,number:a.account_number,balance:a.balance,status:a.status,label:'A2D 데일리 통장'});
async function allPages(path,key){const rows=[];let after=0;while(true){const page=await api(path+'?limit=500&after_id='+after);rows.push(...page);if(page.length<500)return rows;after=page.at(-1)[key]}}
async function loadMe(){const auth=BankAPI.getAuth();if(!auth)return;state.kind=auth.kind;state.user=auth.kind==='staff'?staffUser(await api('/staff/me')):customer(await api('/customers/me'))}
function clearUser(){state.user=null;state.kind=null;renderSeq++;modal.close();$('#modalBody').replaceChildren();$('#panel').replaceChildren();header();home()}
window.addEventListener('bank:auth-lost',()=>{clearUser();toast('로그인이 만료되었습니다. 다시 로그인해 주세요.')});
window.addEventListener('bank:audit-failed',()=>toast('요청은 처리되었지만 감사로그 저장에 실패했습니다. 관리자에게 알려 주세요.'));

function header(){$('#registerButton').textContent=state.user?state.user.name+' 님':'회원가입';$('#registerButton').dataset.action=state.user?'dashboard':'register';$('#loginButton').textContent=state.user?'로그아웃':'로그인 ↗';$('#loginButton').dataset.action=state.user?'logout':'login'}
function showModal(html){$('#modalBody').innerHTML=html;if(!modal.open)modal.showModal()}
function info(title,text){showModal(`<div class="eyebrow">A2D GUIDE</div><h2>${esc(title)}</h2><p>${esc(text)}</p><button class="primary" id="infoClose">확인</button>`);$('#infoClose').onclick=()=>modal.close()}
function formField(label,name,type='text',extra=''){return `<label>${label}<input name="${name}" type="${type}" required ${extra}></label>`}
function login(){showModal(`<div class="eyebrow">WELCOME TO A2D</div><h2>반가워요</h2><p>고객 또는 직원 유형을 선택해 로그인하세요.</p><form id="loginForm" class="form-grid"><label>로그인 유형<select name="kind"><option value="customer">개인 고객</option><option value="staff">은행 직원</option></select></label>${formField('아이디','username','text','autocomplete="username" maxlength="50"')}${formField('비밀번호','password','password','autocomplete="current-password" maxlength="128"')}<label class="remember"><input name="remember" type="checkbox"> 브라우저를 닫아도 로그인 유지 (최대 1시간)</label><div class="form-error" role="alert"></div><button class="primary" type="submit">로그인 →</button></form><div class="demo-guide">고객은 회원가입 후 이용하세요. 최초 직원 계정은 실행 안내의 계정 생성 명령으로 만듭니다.</div>`);bindForm('#loginForm',async d=>{const r=await api('/auth/'+d.kind+'/login','POST',{[d.kind==='staff'?'employee_id':'login_id']:d.username,password:d.password});BankAPI.setAuth(r,d.kind,d.remember==='on');await loadMe();header();modal.close();await workspace(state.user.role==='staff'?'customers':'overview')})}
function register(staff=false){showModal(`<div class="eyebrow">${staff?'STAFF WORKSPACE':'START YOUR BETTER DAY'}</div><h2>${staff?'직원 계정 생성':'A2D 회원가입'}</h2><p>${staff?'직원 계정은 고객 조회와 직원 관리 권한을 가집니다.':'테스트용 이름과 가상 주민번호를 입력하세요.'}</p><form id="registerForm" class="form-grid">${formField('이름',staff?'display_name':'full_name','text','maxlength="100"')}${formField('아이디 · 영문/숫자/_ 4~50자',staff?'employee_id':'login_id','text','pattern="[a-zA-Z0-9_]{4,50}" autocomplete="username" maxlength="50"')}${staff?'':formField('가상 주민번호 · TEST-RRN-숫자 6자리','rrn','text','pattern="TEST-RRN-[0-9]{6}" placeholder="TEST-RRN-123456" maxlength="15" autocomplete="off"')}${formField('비밀번호 · '+(staff?'12':'10')+'자 이상','password','password','minlength="'+(staff?'12':'10')+'" maxlength="128" autocomplete="new-password"')}<p class="form-hint">실제 주민번호와 실제 금융 비밀번호는 입력하지 마세요.</p><div class="form-error" role="alert"></div><button class="primary" type="submit">${staff?'직원 계정 생성':'회원가입 완료하기'}</button></form>`);bindForm('#registerForm',async d=>{await api(staff?'/staff/users':'/customers/signup','POST',d);modal.close();toast(staff?'직원 계정이 생성되었습니다.':'회원가입이 완료되었습니다.');if(staff)await workspace('staff');else login()})}
function bindForm(selector,fn){$(selector).onsubmit=async e=>{e.preventDefault();const f=e.currentTarget,b=f.querySelector('button[type="submit"]'),err=f.querySelector('.form-error');err.textContent='';b.disabled=true;try{await fn(Object.fromEntries(new FormData(f)))}catch(ex){err.textContent=ex.message}finally{b.disabled=false}}}
function home(){$('#homeView').classList.remove('hidden');$('#workspaceView').classList.add('hidden');window.scrollTo({top:0,behavior:'smooth'})}
function title(h,p,button=''){return `<div class="panel-title"><div><h1>${esc(h)}</h1><p>${esc(p)}</p></div>${button}</div>`}
function accountCard(a,verify=true){return `<article class="white-card"><span class="tag">입출금 · 모의 계좌</span><h3>${esc(a.label)}</h3><div class="account-number">${esc(a.number)}</div><small>계좌 ID ${esc(String(a.id))}</small><p><span class="badge">${esc(({ACTIVE:"정상",FROZEN:"동결",CLOSED:"해지"})[a.status]||a.status)}</span></p><div class="amount">${won(a.balance)}</div>${verify?`<div class="card-actions"><button class="secondary" data-pin="${a.id}">계좌 비밀번호 확인</button><button class="secondary" data-history="${a.id}">거래 내역</button><button class="secondary" data-transfer="${a.id}">모의 이체</button></div>`:''}</article>`}
function profile(u){return `<dl class="profile-grid"><dt>${u.role==='staff'?'직원':'고객'} 번호</dt><dd>${u.id}</dd><dt>이름</dt><dd>${esc(u.name)}</dd><dt>아이디</dt><dd>${esc(u.username)}</dd><dt>계정 구분</dt><dd>${role(u.role)}</dd>${u.rrn_last4?'<dt>가상 주민번호</dt><dd>끝 4자리 '+esc(u.rrn_last4)+'</dd>':''}${u.role==='staff'?'<dt>상태</dt><dd>'+(u.active?'활성':'비활성')+'</dd>':''}</dl>`}
let renderSeq=0;
async function workspace(view){if(!state.user){login();return}state.view=view;const seq=++renderSeq;$('#homeView').classList.add('hidden');$('#workspaceView').classList.remove('hidden');$('#sideName').textContent=state.user.name+' 님';$('#roleBadge').textContent=role(state.user.role);const menus=state.user.role==='staff'?[['customers','전체 고객 조회'],['staff','직원 계정 관리'],['events','활동 로그'],...(state.user.authority==='ADMIN'?[['security','보안 기록']]:[]),['lab','실습 환경'],['profile','내 정보']]:[['overview','나의 금융'],['profile','내 정보'],['probe','접근 권한 실습']];$('#sideMenu').innerHTML=menus.map(([id,label])=>`<button data-view="${id}" class="${view===id?'selected':''}">${label}</button>`).join('');$('#crumb').textContent=menus.find(m=>m[0]===view)?.[1]||'상세 조회';$('#panel').innerHTML='<div class="empty">정보를 불러오는 중입니다…</div>';try{
let html='';
if(view==='overview'){const d={accounts:(await api('/accounts/me')).map(account)};html=title('나의 금융','오늘도 반가워요. 나의 계좌를 한눈에 확인하세요.','<button class="primary small" data-action="open">＋ 계좌 만들기</button>')+`<div class="balance-banner"><small>나의 총 모의 잔액</small><h2>${won(d.accounts.reduce((s,a)=>s+a.balance,0))}</h2><p>A2D은행 · 보유 계좌 ${d.accounts.length}개</p></div><div class="account-grid">${d.accounts.map(a=>accountCard(a)).join('')||'<div class="empty">아직 계좌가 없습니다. 첫 계좌를 만들어 보세요.</div>'}</div>`}
if(view==='profile'){await loadMe();html=title('내 정보','가입한 계정 정보를 확인하세요.')+`<div class="white-card">${profile(state.user)}</div>`}
if(view==='customers'){const d={customers:(await allPages('/staff/customers','customer_id')).map(customer)};state.customers=d.customers;html=title('전체 고객 조회','회원 정보와 보유 계좌를 확인할 수 있습니다.')+`<div class="search-row"><input id="customerSearch" aria-label="고객 검색" placeholder="이름 · 아이디 · 고객 번호로 검색"><span class="count">전체 ${d.customers.length}명</span></div><div class="table-box"><table><thead><tr><th>고객 번호</th><th>고객명</th><th>아이디</th><th>가상 주민번호 끝 4자리</th><th>조회</th></tr></thead><tbody id="customerRows">${customerRows(d.customers)}</tbody></table></div>`}
if(view==='staff'){const d={staff:(await allPages('/staff/users','staff_id')).map(staffUser)};html=title('직원 계정 관리','직원 계정의 생성과 활성 상태를 관리합니다.','<button class="primary small" data-action="addStaff">＋ 직원 생성</button>')+`<div class="table-box"><table><thead><tr><th>직원 번호</th><th>이름 / 아이디</th><th>구분</th><th>상태</th><th>관리</th></tr></thead><tbody>${d.staff.map(u=>`<tr><td>${u.id}</td><td><b>${esc(u.name)}</b><br>${esc(u.username)}</td><td>직원</td><td><span class="badge ${u.active?'':'off'}">${u.active?'활성':'비활성'}</span></td><td>${u.id===state.user.id?'본인':`<button data-toggle="${u.id}" data-active="${!u.active}">${u.active?'비활성화':'활성화'}</button>`}</td></tr>`).join('')}</tbody></table></div><p class="form-hint">비활성화하면 해당 직원의 기존 JWT도 무효화됩니다. 비밀번호는 표시하지 않습니다.</p>`}
if(view==='events'||view==='security'){html=await auditPanel(view==='security')}
if(view==='probe'){html=title('접근 권한 실습','본인 또는 다른 테스트 고객 번호로 상세 조회를 요청합니다.')+`<div class="white-card"><form id="probeForm" class="form-grid">${formField('조회할 고객 번호','customer_id','number','min="1" step="1" value="'+state.user.id+'"')}<div class="form-error" role="alert"></div><button type="submit" class="primary">고객 상세 조회</button></form><pre id="probeResult"></pre><p class="form-hint">서버의 수정 모드에서는 다른 고객 조회가 403으로 거부됩니다. 모드는 화면에서 바꿀 수 없습니다.</p></div>`}
if(view==='lab'){const d=await api('/lab');html=title('실습 환경','서버에 설정된 실행 모드를 확인합니다.')+`<div class="lab-info"><span class="badge ${d.mode==='vulnerable'?'off':''}">${d.mode==='fixed'?'수정 모드 · 권한 검사 적용':'취약 모드 · BOLA 실험'}</span><h2>고객 정보 접근 권한 검증</h2><p>일반 고객이 다른 고객 번호로 상세 정보를 요청했을 때,<br>수정 모드는 403 거부 / 취약 모드는 200 응답을 반환합니다.</p><code>GET ${esc(d.endpoint)}</code></div><div class="white-card"><h3>실험 범위</h3><p class="form-hint">로그인은 두 모드 모두 필수입니다. 직원 계정 관리와 계좌 발급 권한은 유지됩니다.<br>모드는 Docker 실행 환경변수로 변경합니다. 웹에서는 변경하지 않습니다.<br>실습 방법은 동봉된 README.md를 참고하세요. Blue 분석은 PowerShell에서 실습 로그를 선택하여 실행합니다.</p></div>`}
if(seq!==renderSeq)return;$('#panel').innerHTML=html;if($('#probeForm'))bindForm('#probeForm',async d=>{const result=await api('/customers/'+encodeURIComponent(d.customer_id));$('#probeResult').textContent=JSON.stringify(result,null,2)});const search=$('#customerSearch');if(search)search.oninput=()=>{const q=search.value.toLowerCase();$('#customerRows').innerHTML=customerRows(state.customers.filter(u=>[u.name,u.username,String(u.id)].some(v=>v.toLowerCase().includes(q))))};
}catch(e){if(seq===renderSeq)$('#panel').innerHTML=`<div class="error-box">${esc(e.message)}</div>`}}

async function auditPanel(securityOnly){
  const logs=await api(securityOnly?'/admin/security/events':'/staff/audit-logs');
  const view=securityOnly?'security':'events';
  const exportButton=securityOnly?'':'<button class="primary small" data-action="export">JSONL 내려받기 ↓</button>';
  const header=title(securityOnly?'보안 기록':'활동 로그','최근 200건 · 요청 처리와 권한 판정을 확인합니다.',exportButton);
  const items=logs.items.map(e=>`<tr>
    <td>${esc(new Date(e.created_at).toLocaleString('ko-KR'))}</td>
    <td>${esc(e.actor_type||'GUEST')} ${esc(String(e.actor_id??''))}</td>
    <td class="mono">${esc(e.http_method)} ${esc(e.request_path)}<br><small>${esc(e.request_id||'')}</small></td>
    <td>${esc(e.required_role||'—')}</td>
    <td>${esc(({allowed:'허용',denied:'거부'})[e.authz_decision]||'—')}</td>
    <td><span class="badge ${e.http_status>=400?'off':''}">${e.http_status??'—'}</span></td>
    <td>${e.duration_ms??'—'} ms</td>
  </tr>`).join('');
  return header+`<div class="search-row"><button class="secondary" data-view="${view}">새로고침 ↻</button>
    <span class="count">표시 ${logs.items.length}건</span></div>
    <div class="table-box"><table><thead><tr><th>시각</th><th>실제 역할</th><th>요청</th>
    <th>필요 역할</th><th>권한 검사</th><th>HTTP</th><th>처리 시간</th>
    </tr></thead><tbody>${items||'<tr><td colspan="7">표시할 기록이 없습니다.</td></tr>'}</tbody></table></div>`;
}

async function transactionHistory(id){
  const data=await api('/accounts/'+encodeURIComponent(id)+'/transactions');
  const rows=data.items.map(t=>`<tr><td>${esc(new Date(t.created_at).toLocaleString('ko-KR'))}</td>
    <td>${esc(t.description||t.transaction_type)}</td><td>${won(t.amount)}</td><td>${won(t.balance_after)}</td></tr>`).join('');
  showModal(`<h2>거래 내역</h2><p>계좌 ID ${esc(id)}</p><div class="table-box"><table>
    <thead><tr><th>시각</th><th>내용</th><th>금액</th><th>거래 후 잔액</th></tr></thead>
    <tbody>${rows||'<tr><td colspan="4">아직 거래 내역이 없습니다.</td></tr>'}</tbody></table></div>`);
}

function simulateTransfer(id){
  showModal(`<h2>모의 이체</h2><p>출금 계좌 ID ${esc(id)}</p><form id="transferForm" class="form-grid">
    ${formField('입금 계좌 ID','destination','number','min="1" step="1" required')}
    ${formField('이체 금액','amount','number','min="1" max="1000000" step="1" required')}
    ${formField('출금 계좌 비밀번호','pin','password','pattern="[0-9]{4}" maxlength="4" inputmode="numeric" required')}
    <div class="form-error" role="alert"></div><button class="primary" type="submit">모의 이체</button></form>`);
  let prior;
  bindForm('#transferForm',async values=>{
    const from=Number(id), to=Number(values.destination), amount=Number(values.amount);
    if(![from,to,amount].every(Number.isSafeInteger))throw new Error('계좌 ID와 금액을 확인해 주세요.');
    const same=prior&&prior.to===to&&prior.amount===amount;
    prior={to,amount,id:same?prior.id:crypto.randomUUID()};
    await api('/transfers','POST',{
      from_account:from,to_account:to,amount,account_pin:values.pin,request_id:prior.id,
    });
    modal.close();
    toast('모의 이체가 완료되었습니다.');
    await workspace('overview');
  });
}

function customerRows(users){return users.map(u=>`<tr><td>${u.id}</td><td><b>${esc(u.name)}</b></td><td>${esc(u.username)}</td><td>${esc(u.rrn_last4)}</td><td><button data-customer="${u.id}">상세 조회 ↗</button></td></tr>`).join('')||'<tr><td colspan="5">검색 결과가 없습니다.</td></tr>'}
async function detail(id){try{const [c,a]=await Promise.all([api('/staff/customers/'+id),api('/staff/customers/'+id+'/accounts')]);const d={customer:customer(c),accounts:a.map(account)};showModal(`<div class="eyebrow">CUSTOMER PROFILE</div><h2>${esc(d.customer.name)} 고객님</h2>${profile(d.customer)}<div class="modal-divider"></div><h3>보유 계좌 ${d.accounts.length}개</h3>${d.accounts.map(a=>accountCard(a,false)).join('')||'<p>개설한 계좌가 없습니다.</p>'}`)}catch(e){toast(e.message)}}
function openAccount(){if(!state.user)return login();if(state.user.role!=='customer')return info('고객 계정에서 이용해 주세요','직원 계정은 고객 조회·관리용입니다. 계좌 발급은 고객 계정으로 로그인해 이용할 수 있습니다.');showModal(`<div class="eyebrow">A2D DAILY ACCOUNT</div><h2>나의 새로운 시작</h2><p>모의 입출금 계좌를 개설합니다. 신규 계좌 잔액은 0원입니다.</p><form id="accountForm" class="form-grid">${formField('계좌 비밀번호 · 숫자 4자리','pin','password','pattern="[0-9]{4}" maxlength="4" inputmode="numeric" autocomplete="new-password"')}${formField('계좌 비밀번호 확인','confirm','password','pattern="[0-9]{4}" maxlength="4" inputmode="numeric" autocomplete="new-password"')}<p class="form-hint">실제 금융 비밀번호를 사용하지 마세요.</p><div class="form-error" role="alert"></div><button class="primary" type="submit">계좌 만들기 →</button></form>`);bindForm('#accountForm',async d=>{if(d.pin!==d.confirm)throw new Error('계좌 비밀번호가 일치하지 않습니다.');await api('/accounts','POST',{account_pin:d.pin});modal.close();toast('새 계좌가 발급되었습니다.');await workspace('overview')})}
function verifyPin(id){showModal(`<div class="eyebrow">ACCOUNT SECURITY</div><h2>계좌 비밀번호 확인</h2><p>개설할 때 설정한 숫자 4자리를 입력하세요.</p><form id="pinForm" class="form-grid">${formField('계좌 비밀번호','pin','password','pattern="[0-9]{4}" maxlength="4" inputmode="numeric"')}<div class="form-error" role="alert"></div><button class="primary" type="submit">확인</button></form>`);bindForm('#pinForm',async d=>{const r=await api('/accounts/'+id+'/verify-pin','POST',{account_pin:d.pin});modal.close();toast(r.message)})}
const actions={home,login,register:()=>register(),products:()=>{home();$('#products').scrollIntoView({behavior:'smooth'})},dashboard:()=>workspace(state.user?.role==='staff'?'customers':'overview'),profile:()=>workspace('profile'),open:openAccount,staff:()=>{if(!state.user)login();else if(state.user.role==='staff')workspace('customers');else info('직원 전용 서비스','직원 계정으로 로그인하면 전체 고객·직원 계정 관리 화면을 사용할 수 있습니다.')},addStaff:()=>register(true),logout:async()=>{try{await api('/auth/logout','POST',{})}catch(e){if(e.status!==401)throw e}BankAPI.clearAuth();clearUser();toast('로그아웃했습니다.')},help:()=>info('A2D은행 이용 안내','회원가입 후 고객 계정으로 로그인해 계좌를 개설할 수 있습니다. 직원 계정은 전체 고객·직원 목록과 로그를 조회합니다. 가상 계좌의 모의 이체와 거래 내역을 확인할 수 있습니다.'),savings:()=>info('목표 저축은 준비 중이에요','현재는 모의 입출금 계좌 발급·조회 기능을 제공합니다. 저축 상품 카드는 디자인 시안입니다.'),export:async()=>{const blob=await BankAPI.request('/staff/audit-logs?format=jsonl','GET',undefined,true);const url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download='a2d-audit.jsonl';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000)}};
document.addEventListener('click',async e=>{const b=e.target.closest('button');if(!b)return;try{if(b.dataset.action)await actions[b.dataset.action]?.();if(b.dataset.view)await workspace(b.dataset.view);if(b.dataset.customer)await detail(b.dataset.customer);if(b.dataset.pin)verifyPin(b.dataset.pin);if(b.dataset.history)await transactionHistory(b.dataset.history);if(b.dataset.transfer)simulateTransfer(b.dataset.transfer);if(b.dataset.toggle){if(!confirm('이 직원의 계정 상태를 변경할까요?'))return;await api('/staff/users/'+b.dataset.toggle,'PATCH',{active:b.dataset.active==='true'});await workspace('staff')}}catch(ex){toast(ex.message)}});
document.querySelectorAll('.brand').forEach(a=>a.onclick=e=>{e.preventDefault();home()});$('#closeModal').onclick=()=>modal.close();modal.addEventListener('click',e=>{if(e.target===modal){const r=modal.getBoundingClientRect();if(e.clientX<r.left||e.clientX>r.right||e.clientY<r.top||e.clientY>r.bottom)modal.close()}});
(async()=>{try{await loadMe();header();if(state.user)await workspace(state.user.role==='staff'?'customers':'overview')}catch(e){if(e.status!==401)toast(e.message)}})();
