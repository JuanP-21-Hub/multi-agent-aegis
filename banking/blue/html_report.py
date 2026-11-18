"""Render the same scoped evidence shown in the Streamlit result."""

from html import escape


def cell(value):
    return escape(str(value)) if value is not None else '—'


def table(headers, rows):
    head = ''.join(f'<th scope="col">{cell(column)}</th>' for column in headers)
    body = ''.join('<tr>' + ''.join(f'<td>{cell(value)}</td>' for value in row) + '</tr>' for row in rows)
    return f'<table><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>'


def authorization_table(logs):
    rows = []
    for log in logs:
        required = log.get('required_role')
        actual = log.get('auth_role')
        decision = log.get('authz_decision')
        if required not in ('CUSTOMER', 'STAFF_OR_ADMIN', 'ADMIN') or not actual or decision not in ('allowed', 'denied'):
            continue
        roles = {'CUSTOMER': {'CUSTOMER'}, 'STAFF_OR_ADMIN': {'STAFF', 'ADMIN'}, 'ADMIN': {'ADMIN'}}
        expected = 'allowed' if actual in roles[required] else 'denied'
        result = {
            ('allowed', 'allowed'): '정책과 일치',
            ('denied', 'denied'): '정책과 일치',
            ('allowed', 'denied'): '추가 조건 확인',
            ('denied', 'allowed'): '추가 확인 필요',
        }[expected, decision]
        rows.append((log['log_id'], actual, required, decision, log.get('status'), result))
    return table(('ID', '실제 역할', '필요 역할', '기록된 판정', 'HTTP', '역할 정책 대조'), rows) if rows else (
        '<p>역할 정책과 대조할 권한 기록이 아직 없습니다.</p>'
    )


def analysis_cards(data):
    cards = []
    for item in data.get('blue_assessments', []):
        title = f"{cell(item['classification'])} / {cell(item['severity'])}"
        actions = ''.join(f'<li>{cell(value)}</li>' for value in item['recommended_actions'])
        refs = ', '.join(cell(value) for value in item['evidence_ids'])
        cards.append(f'<article><h3>{title}</h3><p>{cell(item["summary"])}</p>'
                     f'<p>근거: {refs or "—"}</p><ul>{actions}</ul>'
                     f'<p>한계: {cell(item["limitations"])}</p></article>')
    return ''.join(cards) or '<p>이 실행에서 확인한 모델 판정이 없습니다.</p>'


def render_report(data):
    logs = data['logs']
    server = table(('ID', '시각', '메서드', '경로', 'HTTP', '실제 역할', '필요 역할', '권한 검사'), [
        (item['log_id'], *(item.get(key) for key in
                          ('timestamp', 'method', 'path', 'status', 'auth_role', 'required_role', 'authz_decision')))
        for item in logs
    ])
    source = {'fixture': '예시 로그 · 합성 데이터', 'docker': 'Docker 은행 감사 로그', 'file': '로컬 감사 로그 파일'}
    phase = {'completed': '분석 완료', 'pending': '모델 분석 대기', 'failed': '모델 분석 실패'}
    notes = ''.join(f'<li>{cell(note)}</li>' for note in data.get('analysis_notes', []))
    return f'''<!doctype html>
<html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'">
<title>FinLab Blue 분석 · {cell(data['run_id'])}</title>
<style>
body{{margin:0;background:#f4f7fa;color:#16243b;font:16px/1.6 system-ui,sans-serif}}
main{{max-width:1100px;margin:auto;padding:36px 20px 64px}}h1,h2,h3{{line-height:1.25}}
section{{margin-top:24px}}article,.table-wrap{{overflow:auto;background:white;border:1px solid #dbe2eb;border-radius:12px}}
article{{padding:16px 22px;margin:12px 0}}table{{width:100%;border-collapse:collapse;text-align:left}}
th,td{{padding:10px 12px;border-bottom:1px solid #e1e8f0;white-space:nowrap}}
th{{background:#ebf1f8}}ul:empty{{display:none}}.meta{{color:#435575}}
</style></head><body><main>
<h1>FinLab Blue 분석</h1>
<p class="meta">{cell(source.get(data.get('data_source'),'감사 로그'))} ·
{cell(phase.get(data['analysis_status'], data['analysis_status']))} · 실행 {cell(data['run_id'])}</p>
<p>분석·권고 모드 · {cell(data.get('model_name') or '모델 미실행')}</p>
<section><h2>권한 검사 대조</h2><div class="table-wrap">{authorization_table(logs)}</div></section>
<section><h2>Blue 모델 판정</h2>{analysis_cards(data)}<ul>{notes}</ul></section>
<section><h2>서버 로그</h2><div class="table-wrap">{server}</div></section>
</main></body></html>'''
