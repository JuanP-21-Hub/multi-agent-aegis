# 브랜치 비교 및 통합 명세

2026-11-17에 GitHub 연결로 두 브랜치의 전체 파일을 읽어 비교했다.
백엔드 b73afeeed0a8bb6d6c82f3431de8ddb80b85065e, 화면 11dc0e7eb9b1a21455706c5912e3a9f481b0e0a6을 기준으로 한다.
원본 두 브랜치와 main은 수정하지 않았다. 통합 브랜치는 integration/fastapi-a2d-bank-20261117이다.

## 실제 코드의 API 차이

| 기능 | 팀원 Flask / 화면 | 기존 FastAPI | 통합 처리 |
|---|---|---|---|
| 가입 | POST /api/register: username,name,email,password → message | POST /api/customers/signup: login_id,password,full_name,rrn → customer_id,login_id,full_name,message | 기존 FastAPI 유지, 테스트 RRN 입력 추가, email 제거 |
| 고객 로그인 | POST /api/login: username,password → user,csrf + 쿠키 | POST /api/auth/customer/login: login_id,password → access_token,token_type,expires_in | 고객 로그인 선택, Bearer 토큰 사용 |
| 직원 로그인 | 같은 /api/login | POST /api/auth/staff/login: employee_id,password → 동일 토큰 형식 | 직원 유형 선택 시 employee_id 사용 |
| 본인 정보 | GET /api/me → user,csrf | GET /api/customers/me → customer_id,login_id,full_name | 직원은 새 GET /api/staff/me로 분리 |
| 계좌 개설 | POST /api/accounts: pin → {account:{id,number,label,balance,created}} | POST /api/accounts: account_pin → {account_id,account_number,balance,status} | account_pin으로 전송, 카드에서 번호/잔액/상태 표시 |
| 내 계좌 | GET /api/accounts → {accounts:[...]} | GET /api/accounts/me → 배열 | 경로와 배열 응답 반영 |
| 고객 목록 | GET /api/customers → {customers:[...]} | GET /api/staff/customers → 배열, 기존 최대100 | 경로 변경, after_id/limit 추가 및 화면의 전체 페이지 로딩 |
| 직원 고객 상세 | GET /api/customers/{id} → {customer,accounts} | GET /api/staff/customers/{id}, GET /api/staff/customers/{id}/accounts | 두 API를 각각 호출, rrn_last4 표시 |
| PIN 확인 | POST /api/accounts/{id}/verify-pin: pin | 없음 | 같은 기능을 FastAPI에 추가, account_pin 사용 |
| 직원 관리 | GET/POST /api/staff, PATCH /api/staff/{id}: active | 생성 CLI만 있음 | GET/POST /api/staff/users, PATCH /api/staff/users/{id} |
| 로그 | GET /api/events, ?format=jsonl | audit_logs 테이블만 존재 | GET /api/staff/audit-logs, ?format=jsonl, 자동 기록 |
| BOLA | GET /api/customers/{id}, env LAB_MODE | 없음 | 동일 개념의 고객 전용 상세 엔드포인트, 기본 fixed |
| 로그아웃 | POST /api/logout: DB session 제거 | 없음 | POST /api/auth/logout: token_version 증가 |

기존 9개 API의 이름과 핵심 요청·응답 형식은 유지했다.
직원 목록 API는 기본 limit=100을 유지하면서 최대500의 keyset 페이지 조회를 지원한다.
권한이 다른 유효한 토큰은 403, 미인증/만료/무효/비활성 직원 토큰은 401을 반환한다.

## 실제 DB 차이

| 팀원 테이블/컬럼 | 기준 FastAPI 테이블/컬럼 | 처리 |
|---|---|---|
| users: id,username,name,email,password,role,active | customers: id,login_id,password_hash,full_name,rrn_encrypted,rrn_last4,created_at | customers 유지; 이메일 UI 제거; 고객과 직원 테이블 분리 유지 |
| 같은 users 테이블의 staff 행 | staff_users: id,employee_id,password_hash,display_name,role,created_at | active,token_version만 추가 |
| accounts: id,owner_id,number,label,pin,balance,created | accounts: id,customer_id,account_number,account_pin_hash,balance,status,created_at | 기존 FastAPI 스키마 유지, label은 화면 문구 |
| sessions: token,user_id,csrf,expires | 없음 / JWT | sessions를 만들지 않음 |
| events: id,request_id,at,actor_id,role,method,path,target_id,status,duration_ms | audit_logs: id,actor_type,actor_id,action,target_type,target_id,request_path,ip_address,status,details,created_at | 기존 테이블에 요청 측정 컬럼 추가 |
| attempts: key,count,until | 없음 | 가져오지 않음; 현재 통합 버전은 원본 Flask의 시도 횟수 제한을 제공하지 않음 |
| 없음 | transactions: id,account_id,transaction_type,amount,balance_after,description,created_at | 테이블과 기존 데이터 보존, 입금·출금·이체 API는 추가하지 않음 |

## 추가 DB 컬럼

| 테이블 | 추가 항목 | 이유 |
|---|---|---|
| customers | token_version BIGINT NOT NULL DEFAULT 0 | 서버 로그아웃 시 기존 JWT 무효화 |
| staff_users | active BOOLEAN NOT NULL DEFAULT TRUE | 직원 활성/비활성 관리 |
| staff_users | token_version BIGINT NOT NULL DEFAULT 0 | 비활성화/재활성화 이후 옛 JWT 재사용 방지 |
| audit_logs | request_id UUID, http_method VARCHAR(10), http_status INTEGER, duration_ms INTEGER | 요청 추적 및 처리 결과/시간 |
| audit_logs | idx_audit_logs_id_desc 인덱스 | 최신 로그/keyset 페이지 조회 |

원래 status SUCCESS/FAILURE는 유지하고 HTTP 상태코드는 http_status에 따로 저장한다.
기존 데이터의 암호문/해시/ID/관계/잔액/상태는 바꾸지 않는다. 기존 JWT는 ver 누락 시 0으로 해석한다.

## 추가 API 계약

| 메서드·경로 | 권한 | 요청 / 응답 |
|---|---|---|
| GET /api/staff/me | STAFF/ADMIN | staff_id,employee_id,display_name,role,active |
| POST /api/auth/logout | 고객/직원 | 해당 계정 token_version 증가, message |
| POST /api/accounts/{account_id}/verify-pin | 소유 고객 | {account_pin:"숫자4자리"} → {verified:true,message} |
| GET /api/staff/users | STAFF/ADMIN | after_id=0,limit=100 → 직원 배열 |
| POST /api/staff/users | STAFF/ADMIN | employee_id,display_name,password(12~128자) → 직원; role은 서버가 STAFF로 고정 |
| PATCH /api/staff/users/{staff_id} | STAFF/ADMIN | {active:true/false} → 직원; 본인 변경 400 |
| GET /api/staff/audit-logs | STAFF/ADMIN | format=json/jsonl,limit=200(최대1000),before_id → {items,next_before_id} 또는 JSONL |
| GET /api/customers/{customer_id} | 고객 | fixed: 본인만; vulnerable: 다른 고객 허용. customer_id,login_id,full_name만 반환 |
| GET /api/lab | STAFF/ADMIN | mode,endpoint,scenario; 읽기 전용 |

## 수정 파일과 이유

| 파일 | 변경 이유 |
|---|---|
| banking/backend/app/main.py | 기존 해시/암호화/JWT/API 유지, active/버전 검사, 직원 본인 정보 지원, 고객 목록 페이지 처리 |
| banking/backend/app/extensions.py | PIN·직원관리·로그아웃·감사로그·BOLA 및 민감값 없는 오류 처리 |
| banking/frontend/index.html, style.css | 팀원 홈/카드/모달/레이아웃 유지, 공통 API 스크립트와 로그인 유형 입력 스타일 추가 |
| banking/frontend/app.js | 기존 디자인의 화면을 실제 FastAPI 계약에 맞춰 연결, 이메일 제거, 가상 RRN/상태 표시 |
| banking/frontend/api.js | Bearer 헤더, 로그인 저장/복원/만료/다운로드/오류 처리를 한곳으로 통합 |
| banking/database/migrations/001_integration.sql | 기존 DB에 안전한 컬럼/인덱스 추가, 재실행 가능 |
| banking/compose.yaml, nginx.conf | Nginx 동일 출처 /api 프록시, 마이그레이션 성공 후 기동, DB/백엔드 내부 연결 |
| banking/compose.existing.yaml | 원래 볼륨을 정확한 이름으로 재사용 |
| banking/scripts/init-env.sh | 새 설치의 무작위 비밀값 생성; 기존 .env 덮어쓰기 거부 |
| banking/backend/tests, banking/tests, scripts/test-compose.sh | 실제 DB/API/브라우저/재시작 및 기존 데이터 보존 테스트 |
| .github/workflows/banking-integration.yml | 통합 브랜치에서만 격리 Compose 검증 |

## 보안과 동작 범위

- 로그인/PIN은 기존 Argon2, 가상 RRN은 기존 Fernet, JWT HS256의 issuer/audience/만료 검증을 유지한다.
- 이메일은 DB가 지원하지 않으므로 제거했다. 저장되지 않는 입력 항목을 남기지 않았다.
- JWT에는 신원/역할/버전/발급·만료 정보만 포함하고 비밀번호/PIN/RRN은 넣지 않는다.
- 감사로그는 본문·헤더·쿼리문자열을 수집하지 않는다. 경로는 라우트 템플릿, 조회 대상 ID는 별도 컬럼이다.
- 과거 audit_logs.details는 읽기/다운로드에서 제외한다. 미등록 과거 경로도 정규화한다.
- 422 오류에서 입력 원문/input/ctx를 제거한다. 앱/Nginx access log도 끄며 비밀값이 포함된 원문 경로를 기록하지 않는다.
- 감사로그 DB 쓰기 실패는 응답 헤더 X-Audit-Persisted=false 및 화면 알림으로 드러낸다. 이미 처리된 금융 요청을 되돌리지는 않는다.
- BOLA는 고객 상세 한 곳의 소유권 검사만 변경한다. 직원 권한, PIN 소유권, 로그인 검사는 두 모드 모두 유지된다.
- 팀원의 5계좌 제한은 기준 백엔드 계약에 없으므로 안내에서 제거했다. 계좌는 기존 FastAPI 규칙을 따른다.
- 이 프로젝트는 로컬 실습용이며 인터넷 공개 배포하지 않았다. TLS, 로그인/PIN 횟수 제한, 대규모 로그 보관/정리는 별도 운영 보완 사항이다.
