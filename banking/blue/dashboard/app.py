"""ATTACK2DEFENSE: presentation dashboard (read-only)."""
import html
import json
import os
from pathlib import Path
import streamlit as st
from domain import DataError, groups, read_data, sample

ROOT = Path(__file__).parent
st.set_page_config(page_title='ATTACK2DEFENSE · 금융 보안 분석', page_icon='🛡', layout='wide', initial_sidebar_state='collapsed')
def e(value):
    return html.escape(str(value), quote=True)

def markup(value):
    st.html(value)

markup('''<style>
@import url('');
html,body,[class*="css"],button,input,textarea{font-family:"Noto Sans CJK KR","Malgun Gothic",sans-serif}
.stApp{background:#F5F7FC;color:#172B4D}
.block-container{max-width:1480px;padding-top:2.1rem;padding-bottom:2.3rem}
header[data-testid="stHeader"]{background:transparent}
h1,h2,h3{letter-spacing:-.035em}
[data-testid="stTabs"] [data-baseweb="tab-list"]{gap:28px;border-bottom:1px solid #dfe6f1;background:transparent}
[data-testid="stTabs"] [data-baseweb="tab"]{font-size:16px;font-weight:650;padding:15px 4px}
[data-testid="stTabs"] [data-baseweb="tab-highlight"]{background:#2458d3;height:3px}
.hero{display:flex;justify-content:space-between;align-items:center;gap:22px;margin-bottom:18px}
.brand{font-size:12px;font-weight:800;color:#2458d3;letter-spacing:2px;margin:0 0 9px}
.hero h1{font-size:34px;margin:0 0 10px;line-height:1.25;color:#142b49;font-weight:800}
.sub{font-size:14px;color:#68778d;margin:0;line-height:1.7}
.hero-right{text-align:right;flex-shrink:0}
.run{font-size:12px;color:#74839a;margin-top:9px}
.chip{display:inline-block;padding:5px 10px;border-radius:6px;font-size:12px;font-weight:700;background:#edf2fa;color:#52647d;white-space:nowrap;flex-shrink:0}
.chip.blue{background:#eaf0ff;color:#2458d3}.chip.teal{background:#e7f5f3;color:#137c70}.chip.amber{background:#fff3dc;color:#946014}.chip.red{background:#fff0ed;color:#ba4d3f}
.example{border:1px solid #e3dcc6;background:#fffbef;color:#846730;border-radius:9px;padding:9px 14px;font-size:12px;line-height:1.6;margin:0 0 20px}
.stat{background:#fff;border:1px solid #e4eaf3;border-radius:12px;padding:16px 20px;margin:5px 0 22px;min-height:111px}
.stat-label{font-size:12px;color:#738198;margin:0 0 5px}.stat-value{font-size:29px;line-height:1.3;font-weight:800;color:#172b4d}.stat-note{font-size:11px;color:#7f8ba0;margin-top:4px}
.panel{background:#fff;border:1px solid #e0e7f1;border-radius:14px;overflow:hidden;min-height:400px;margin-bottom:12px}
.panel-head{padding:22px 24px 19px;border-bottom:1px solid #edf0f6;background:#fcfdff;border-top:4px solid #3869da}
.panel.teal .panel-head{border-top-color:#169487}.panel-kicker{font-size:10px;font-weight:800;color:#6a7d96;letter-spacing:1.4px;margin-bottom:8px}
.panel h2{font-size:21px;font-weight:750;margin:0 0 7px;color:#172b4d}.panel-desc{color:#768397;font-size:12px;line-height:1.7}
.panel-body{padding:0 23px}.incident{padding:20px 0;border-bottom:1px solid #edf0f6}.incident:last-child{border-bottom:none}
.incident-top{display:flex;align-items:flex-start;gap:8px;justify-content:space-between}.incident h3{flex:1;min-width:0;word-break:keep-all;font-size:17px;margin:0;line-height:1.5;font-weight:750;letter-spacing:-.025em}
.meta{font-size:11px;color:#7e8b9f;margin:8px 0}.reason{font-size:13px;color:#52627a;line-height:1.85;margin:9px 0 12px}.tiny{font-size:11px;color:#7b8ba0;line-height:1.7}
.tags{display:flex;gap:6px;flex-wrap:wrap}.tags span{background:#f2f5fa;color:#687b94;border-radius:4px;font-size:10px;padding:3px 7px}
.empty{padding:60px 22px;color:#79879b;text-align:center;line-height:1.9;font-size:14px}.empty strong{color:#40546f;font-size:17px}
.context{margin-top:12px;color:#75849b;font-size:12px;line-height:1.8}.section-label{font-size:12px;font-weight:750;letter-spacing:1px;color:#627695;margin-bottom:10px}
.detail{border:1px solid #e0e7f1;border-radius:12px;background:#fff;padding:24px 26px;margin:12px 0 20px}.detail h2{margin:9px 0 12px;font-size:25px;letter-spacing:-.04em}.detail p{font-size:14px;line-height:1.9;color:#52627a}
.action{padding:17px 20px;background:#fff;border:1px solid #e1e8f1;border-radius:10px;margin:10px 0;display:flex;gap:17px;align-items:flex-start}.action-num{color:#2458d3;background:#edf2ff;font-size:12px;padding:5px 9px;border-radius:6px;font-weight:800}.action-text{font-size:15px;line-height:1.8;color:#324963}
.note{padding:16px 18px;background:#edf2fa;border-radius:9px;font-size:13px;line-height:1.85;color:#5d708b;margin:12px 0}.note b{display:block;color:#294367;margin-bottom:4px}
.footer{margin-top:27px;border-top:1px solid #e0e7f1;padding-top:14px;display:flex;justify-content:space-between;color:#93a0b3;font-size:11px}
@media(max-width:800px){.hero{display:block}.hero-right{text-align:left;margin-top:12px}.hero h1{font-size:26px}.panel{min-height:0}.block-container{padding-top:1.4rem}.footer{display:block}}
</style>'''.replace("@import url('');",''))

with st.sidebar:
    st.markdown('### 화면 설정')
    source = st.radio('데이터', ['예시 데이터', '실제 결과 파일'])
    if source == '예시 데이터':
        mode = st.selectbox('예시 상태', ['추가 탐지 확인','평가 대기','정상 업무','분석 실패'])
        data = sample(mode)
    else:
        root = Path(os.environ.get('DASHBOARD_DATA_DIR', str(ROOT/'runs')))
        paths = sorted(root.glob('*/evaluation.json'), reverse=True) if root.exists() else []
        if not paths:
            st.info('아직 결과가 없습니다. 실행별 evaluation.json을 연결하면 표시됩니다.')
            data = None
        else:
            selected = st.selectbox('실행 선택', paths, format_func=lambda p:p.parent.name)
            try:
                data = read_data(selected)
            except DataError as ex:
                st.error(str(ex))
                data = None
    st.button('결과 새로고침', width='stretch')
    st.caption('결과 표시 전용 · 모델과 공격을 실행하지 않습니다.')
    st.markdown('---')
    st.caption('ATTACK2DEFENSE / Capstone Design')

if data is None:
    st.title('금융 보안 분석 대시보드')
    st.info('결과를 기다리고 있습니다. 왼쪽 설정에서 실행 결과를 선택하세요.')
    st.stop()

left, right, unassigned, rejected = groups(data)
status_labels={'completed':'분석 완료','pending':'분석 대기','running':'분석 중','failed':'분석 실패'}
status=data['analysis_status']
source_label = {'docker': 'Docker 은행 감사 로그', 'fixture': '합성 로그', 'file': '로컬 감사 로그'}
if data.get('data_source') in source_label:
    st.caption(source_label[data['data_source']])
markup(f'''<div class="hero"><div><div class="brand">ATTACK2DEFENSE</div><h1>금융 보안 분석 대시보드</h1><p class="sub">기존 검사와 블루 LLM의 판단을 비교하고, 근거와 대응 방법을 확인합니다.</p></div><div class="hero-right"><span class="chip {'red' if status=='failed' else 'blue'}">{status_labels[status]}</span><div class="run">{e(data['run_id'])} · {e(data['updated_at'])}</div></div></div>''')
if source == '예시 데이터':
    markup('<div class="example">예시 데이터 화면입니다. 실제 공격·모델 분석 결과가 아니며, 시나리오와 수치는 화면 확인을 위한 샘플입니다.</div>')
else:
    st.caption(f"선택한 실험: {data['title']}")
if status != 'completed':
    st.warning('분석이 완료되지 않았습니다. 현재 화면의 일부 결과만으로 공격 유무나 탐지 성능을 확정하지 않습니다.')

compare, actions, evidence = st.tabs(['탐지 비교', '대응 권고', '근거 및 평가'])
validation_labels={'confirmed_attack':'공격 대조 확인','pending':'평가 대기','false_positive':'오탐 확인'}
validation_colors={'confirmed_attack':'teal','pending':'amber','false_positive':'red'}

def finding_html(f):
    badge=validation_labels[f['validation']]
    color=validation_colors[f['validation']]
    tags=''.join(f'<span>{e(x)}</span>' for x in f['evidence_log_ids'])
    return f'''<div class="incident"><div class="incident-top"><h3>{e(f['title'])}</h3><span class="chip {color}">{badge}</span></div><div class="meta">{e(f.get('account','계정 미제공'))} &nbsp; / &nbsp; {e(f.get('time','시각 미제공'))}</div><p class="reason">{e(f['reason'])}</p><div class="tags">{tags or '<span>근거 미제공</span>'}</div></div>'''

def panel(title, kicker, desc, items, kind):
    body=''.join(finding_html(f) for f in items)
    if not body:
        body='<div class="empty"><strong>표시할 사건이 없습니다</strong><br>'+('분석 완료 결과에서 현재 분류에 해당하는 사건이 없습니다.' if status=='completed' else '분석 완료를 기다리고 있습니다.')+'</div>'
    markup(f'<section class="panel {kind}"><div class="panel-head"><div class="panel-kicker">{kicker}</div><h2>{title} <span class="chip {kind}">{len(items)}건</span></h2><div class="panel-desc">{desc}</div></div><div class="panel-body">{body}</div></section>')

with compare:
    confirmed=sum(f['validation']=='confirmed_attack' for f in right)
    pending=sum(f['validation']=='pending' for f in right)
    cols=st.columns(4)
    for col,label,value,note in zip(cols,['기본 검사 경보','블루 추가 탐지 확인','추가 의심 · 평가 대기','오탐으로 확인'],[len(left),confirmed,pending,len(rejected)],['사전 검사 항목에 해당','기본 검사 미탐지 · 공격 대조 확인','아직 공격으로 확정하지 않은 사건','추가 탐지 성과에 포함하지 않음']):
        with col:
            shown=str(value)+'건' if status=='completed' else '—'
            markup(f'<div class="stat"><div class="stat-label">{label}</div><div class="stat-value">{shown}</div><div class="stat-note">{note}</div></div>')
    a,b=st.columns(2,gap='large')
    with a:
        panel('기존 검사에서 확인한 공격', 'BASELINE DETECTION', '실무자의 검사 항목을 모사한 기본 검사 결과 · 평가 전에는 경보 후보',left,'blue')
    with b:
        panel('블루가 추가로 의심한 공격', 'BLUE LLM FINDINGS', '기존 검사에 잡히지 않은 사건 · 실제 공격 대조 여부를 함께 표시',right,'teal')
    markup('<div class="context">두 영역은 기본 검사 결과를 기준으로 나눕니다. 오른쪽은 기존 검사에 등록되지 않은 공격의 징후를 확인하는 영역이며, 제로데이 발견이나 사람의 탐지 불가능성을 의미하지 않습니다.</div>')
    if unassigned:
        st.info(f'기본 검사 결과가 아직 없는 사건 {len(unassigned)}건은 비교 영역에 배정하지 않았습니다. 근거 및 평가 탭에서 확인하세요.')
    if rejected:
        with st.expander(f'오탐으로 확인한 사건 {len(rejected)}건'):
            for f in rejected:
                st.write(f"{f['finding_id']} · {f['title']}")

with actions:
    actionable=[f for f in data['findings'] if f['blue_detected'] and f['validation']!='false_positive']
    if not actionable:
        st.info('현재 표시할 블루 대응 권고가 없습니다.' if status=='completed' else '분석 완료 후 대응 권고가 표시됩니다.')
    else:
        selected_id=st.selectbox('분석할 사건', [f['finding_id'] for f in actionable],format_func=lambda x:next(f['title'] for f in actionable if f['finding_id']==x),key='action_finding')
        f=next(f for f in actionable if f['finding_id']==selected_id)
        markup(f'<div class="detail"><span class="chip {validation_colors[f["validation"]]}">{validation_labels[f["validation"]]}</span><h2>{e(f["title"])}</h2><p>{e(f["reason"])}</p><div class="tiny">{e(f["finding_id"])} · {e(f.get("account","계정 미제공"))}</div></div>')
        a,b=st.columns([1.5,1],gap='large')
        with a:
            markup('<div class="section-label">권고하는 대응 방법</div>')
            for i,rec in enumerate(f['recommendations'],1):
                markup(f'<div class="action"><span class="action-num">{i:02d}</span><div class="action-text">{e(rec)}</div></div>')
            if not f['recommendations']:
                st.info('전달된 대응 권고가 없습니다.')
            st.caption('권고 제시 단계입니다. 실제 차단이나 계정 제한을 실행하지 않습니다.')
        with b:
            markup(f'<div class="note"><b>업무 영향</b>{e(f.get("business_impact","정보 미제공"))}</div>')
            markup(f'<div class="note"><b>조치 후 확인</b>{e(f.get("next_check","정보 미제공"))}</div>')
            uncertain='<br>'.join(e(x) for x in f.get('uncertainties',[])) or '추가 정보 미제공'
            markup(f'<div class="note"><b>아직 확인이 필요한 부분</b>{uncertain}</div>')
        with st.expander('이 권고의 근거 로그 보기',expanded=False):
            st.dataframe([l for l in data['logs'] if l['log_id'] in f['evidence_log_ids']],width='stretch',hide_index=True)

with evidence:
    st.markdown('#### 사건별 탐지·평가 결과')
    for note in data.get('analysis_notes', []):
        st.text(note)
    st.caption('탐지 성공과 공격 성공은 별개입니다. 대응 권고의 적절성은 사람이 검토합니다.')
    rows=[]
    for f in data['findings']:
        rows.append({'사건':f['finding_id'],'의심 상황':f['title'],'기본 검사':'미평가' if f['baseline_detected'] is None else '탐지' if f['baseline_detected'] else '미탐지','블루':'탐지' if f['blue_detected'] else ('미탐지' if status=='completed' else '결과 미완료'),'실제 공격 대조':validation_labels[f['validation']]})
    if rows:
        st.dataframe(rows,width='stretch',hide_index=True)
    else:
        st.info('전달된 사건별 평가 결과가 없습니다.')
    st.markdown('#### 근거 기록')
    if data['findings']:
        ids=['전체 기록']+[f['finding_id'] for f in data['findings']]
        target=st.selectbox('사건별 근거 필터',ids,key='log_filter')
        refs=None if target=='전체 기록' else next(f['evidence_log_ids'] for f in data['findings'] if f['finding_id']==target)
    else:
        refs=None
    logs=[l for l in data['logs'] if refs is None or l['log_id'] in refs]
    if logs:
        st.dataframe(logs,width='stretch',hide_index=True)
    else:
        st.info('표시할 로그가 없습니다.')
    st.download_button('현재 결과 JSON 내려받기',data=json.dumps(data,ensure_ascii=False,indent=2),file_name='dashboard_result.json',mime='application/json')
    with st.expander('실행 정보'):
        st.write({'실행 번호':data['run_id'],'분석 상태':status_labels[status],'모델':data.get('model_name','미제공'),'갱신 시각':data['updated_at']})
markup('<div class="footer"><span>ATTACK2DEFENSE · 금융 정보 보호 실험</span><span>근거를 확인하고, 대응을 판단합니다.</span></div>')
