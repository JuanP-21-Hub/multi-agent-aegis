"""Read-only dashboard data contract. No model loading or attack execution."""
import copy
import json
from pathlib import Path

class DataError(ValueError):
    pass

STATUSES = {'completed', 'pending', 'running', 'failed'}
VALIDATIONS = {'confirmed_attack', 'false_positive', 'pending'}

def validate(data):
    if not isinstance(data, dict) or data.get('schema_version') != '1.0':
        raise DataError('schema_version은 1.0이어야 합니다.')
    for key in ('run_id', 'title', 'updated_at', 'analysis_status', 'findings', 'logs'):
        if key not in data:
            raise DataError(f'필수 항목이 없습니다: {key}')
    for key in ('run_id', 'title', 'updated_at'):
        if not isinstance(data[key], str) or not data[key].strip():
            raise DataError(f'{key}는 비어 있지 않은 문자열이어야 합니다.')
    if data['analysis_status'] not in STATUSES:
        raise DataError('analysis_status 값이 잘못되었습니다.')
    if not isinstance(data['findings'], list) or not isinstance(data['logs'], list):
        raise DataError('findings와 logs는 배열이어야 합니다.')
    notes = data.get('analysis_notes', [])
    if not isinstance(notes, list) or any(not isinstance(note, str) for note in notes):
        raise DataError('analysis_notes는 문자열 배열이어야 합니다.')
    log_ids = set()
    for log in data['logs']:
        if not isinstance(log, dict) or not isinstance(log.get('log_id'), str):
            raise DataError('로그에는 문자열 log_id가 필요합니다.')
        if log['log_id'] in log_ids:
            raise DataError('중복 log_id가 있습니다.')
        log_ids.add(log['log_id'])
    ids = set()
    for f in data['findings']:
        if not isinstance(f, dict):
            raise DataError('사건 항목은 객체여야 합니다.')
        for k in ('finding_id','title','reason','baseline_detected','blue_detected','validation','evidence_log_ids','recommendations'):
            if k not in f:
                raise DataError(f'사건의 필수 항목이 없습니다: {k}')
        for k in ('finding_id', 'title', 'reason'):
            if not isinstance(f[k], str) or not f[k].strip():
                raise DataError(f'사건의 {k}는 문자열이어야 합니다.')
        if f['finding_id'] in ids:
            raise DataError('중복 finding_id가 있습니다.')
        ids.add(f['finding_id'])
        if f['validation'] not in VALIDATIONS:
            raise DataError('사건 validation 값이 잘못되었습니다.')
        if not (f['baseline_detected'] is None or type(f['baseline_detected']) is bool):
            raise DataError('baseline_detected는 true, false 또는 null이어야 합니다.')
        if type(f['blue_detected']) is not bool:
            raise DataError('blue_detected는 true 또는 false이어야 합니다.')
        if not isinstance(f['evidence_log_ids'], list) or any(not isinstance(x,str) for x in f['evidence_log_ids']):
            raise DataError('evidence_log_ids는 문자열 배열이어야 합니다.')
        if set(f['evidence_log_ids']) - log_ids:
            raise DataError(f"존재하지 않는 근거 로그가 있습니다: {f['finding_id']}")
        if not isinstance(f['recommendations'], list) or any(not isinstance(x,str) for x in f['recommendations']):
            raise DataError('recommendations는 문자열 배열이어야 합니다.')
        for k in ('uncertainties',):
            if k in f and (not isinstance(f[k],list) or any(not isinstance(x,str) for x in f[k])):
                raise DataError(f'{k}는 문자열 배열이어야 합니다.')
        for k in ('account','time','business_impact','next_check'):
            if k in f and not isinstance(f[k],str):
                raise DataError(f'{k}는 문자열이어야 합니다.')
        if 'severity' in f and f['severity'] not in {'high','medium','low'}:
            raise DataError('severity는 high, medium, low 중 하나여야 합니다.')
    return data

def read_data(path):
    try:
        p = Path(path)
        if p.stat().st_size > 5_000_000:
            raise DataError('결과 파일은 5MB 이하로 전달해주세요.')
        return validate(json.loads(p.read_text(encoding='utf-8')))
    except (OSError, ValueError, TypeError) as e:
        if isinstance(e, DataError):
            raise
        raise DataError(f'결과 파일을 읽을 수 없습니다: {type(e).__name__}') from e

def groups(data):
    visible = [f for f in data['findings'] if f['validation'] != 'false_positive']
    left = [f for f in visible if f['baseline_detected'] is True]
    right = [f for f in visible if f['baseline_detected'] is False and f['blue_detected'] is True]
    unassigned = [f for f in visible if f['baseline_detected'] is None]
    rejected = [f for f in data['findings'] if f['validation'] == 'false_positive']
    return left, right, unassigned, rejected

def sample(mode='추가 탐지 확인'):
    data = read_data(Path(__file__).parent/'examples'/'evaluation.json')
    data = copy.deepcopy(data)
    if mode == '평가 대기':
        for f in data['findings']:
            f['validation'] = 'pending'
    elif mode == '정상 업무':
        data['title'] = '승인된 고객 조회 업무'
        data['findings'] = []
        data['logs'] = [data['logs'][0]]
    elif mode == '분석 실패':
        data['analysis_status'] = 'failed'
        data['findings'] = []
    return data
