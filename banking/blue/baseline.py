"""FinLab baseline rules for interpreting passive audit records."""


def classify(event):
    path, code, decision = event.get('path', ''), event.get('status'), event.get('authz_decision')
    if decision == 'rate_limited_backend' or code == 429:
        return ('blocked', 'medium', '요청 제한', '백엔드가 반복 요청을 제한했습니다.')
    if code in (401, 403) and path.startswith('/api/auth/'):
        return ('login', 'low', '로그인 실패', '인증 실패 기록입니다. 단일 실패만으로 침입을 확정할 수 없습니다.')
    if code in (401, 403):
        return ('blocked', 'medium', '보호 기능 접근 거절', '인증 또는 접근 권한 검사에서 거절되었습니다.')
    if path == '/api/transfers' and code == 422:
        return ('blocked', 'medium', '송금 입력 거절', '금액 또는 계좌 입력값이 유효하지 않아 거절되었습니다.')
    if isinstance(code, int) and code >= 500:
        return ('error', 'medium', '서버 오류', '서버 오류가 발생했습니다. 침입 성공을 뜻하지 않습니다.')
    return None
