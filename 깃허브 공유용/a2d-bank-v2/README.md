# A2D은행 v2 — 창훈 담당 웹 실습 패키지

은행 메인 + 회원가입·로그인 + 고객 화면 + 계좌 발급·비밀번호 + 직원 전용 관리 + DB + BOLA 실습.
실제 은행과 무관한 가상 금융 교육용 프로젝트입니다. 테스트 정보만 사용합니다.


## 디자인 수정 사항 (2026-11-16)

- A2D 은행 고유 이름과 모든 계정/계좌/고객/로그/API 기능 유지.
- 우리은행 공식 CI의 블루 계열을 색상 참고로 사용(딥 블루 `#0067AC`, 블루 `#0083CA`, 라이트 블루 `#20C4F4`). 우리은행 로고, 상표, UI 화면은 복제하지 않음.
- 메인 그래픽 위의 말풍선/캡슐형 플로팅 배지, 체크 아이콘, 화살표 배지, 코인 장식 제거. 카드 그래픽은 단정한 수평 형태로 변경.
- 전 페이지 배경/버튼/직원 업무/로그/입력창 색을 블루/화이트/네이비 계열로 통일.
- 백엔드 및 데이터베이스 코드는 변경하지 않음. **기존 DB를 보존하려면 `docker compose down -v`를 실행하지 말 것**. 디자인 변경 후 브라우저에서 `Ctrl+F5`로 새로고침.

## 1. 팀원 실행 방법 (Windows / Ubuntu / WSL)

**필수:** Docker Desktop(Windows + WSL) 또는 Docker Engine + Compose v2가 설치되어 있어야 합니다. Windows는 Docker Desktop에서 Linux containers를 사용하고, WSL 우분투에서 실행할 때는 Docker Desktop의 WSL Integration을 활성화하세요. `docker compose version`으로 확인합니다.

### GitHub 저장소에서 내려받아 실행

아래 명령은 **이 `a2d-bank-v2/` 폴더가** `JuanP-21-Hub/multi-agent-aegis` 저장소 루트에 포함되어 있고 `main`에 병합된 후를 기준으로 합니다. `git`과 `docker`가 설치된 Windows PowerShell, Git Bash 또는 Ubuntu 터미널에서 실행할 수 있습니다.

```bash
git clone https://github.com/JuanP-21-Hub/multi-agent-aegis.git
cd multi-agent-aegis/a2d-bank-v2
docker compose up -d --build
```

아직 `main`에 병합하기 전이고 `feature/a2d-bank-web` 브랜치에 업로드된 상태라면:

```bash
git clone --branch feature/a2d-bank-web https://github.com/JuanP-21-Hub/multi-agent-aegis.git
cd multi-agent-aegis/a2d-bank-v2
docker compose up -d --build
```

GitHub 저장소가 비공개면 초대받고 수락한 계정으로 인증해야 합니다.

**브라우저 접속:** <http://localhost:8081> (실행한 **그 컴퓨터**에서 접속). HTML 파일을 직접 열면 API가 연결되지 않습니다. `localhost`는 인터넷 공개 주소가 아닙니다.

### ZIP으로 받은 경우

ZIP을 압축 해제한 뒤, `compose.yaml` 파일이 들어 있는 **`a2d-bank-v2` 폴더** 안에서 터미널을 열고 다음을 실행합니다.

```bash
docker compose up -d --build
```

확인 및 중지:

```bash
docker compose ps
docker compose logs --tail=60 backend
docker compose down
```

`docker compose down`은 테스트 데이터를 유지합니다. `down -v`는 DB까지 삭제하므로 주의하세요. 8081 포트가 이미 사용 중이면 실행 중인 기존 A2D 컨테이너와 중복되는지 확인하세요.

## 2. 테스트 계정

| 역할 | 아이디 | 비밀번호 |
|---|---|---|
| 직원 = 관리자 | staff | DemoBank!2026 |
| 고객 A / 고객 번호 2 | customer1 | DemoBank!2026 |
| 고객 B / 고객 번호 3 | customer2 | DemoBank!2026 |

기본 고객 계좌의 계좌 비밀번호는 `1234`입니다.
신규 가입한 고객의 계좌는 없으며 직접 발급하면 0원으로 시작합니다.
기본 고객 A는 모의 잔액 1,250,000원, B는 2,840,000원을 갖습니다.
로그인 세션은 최대 2시간 유지됩니다.

## 3. 시연 순서

1. 메인 → 회원가입 → 테스트 이름·아이디·이메일·10자 이상 비밀번호 입력.
2. 새 고객으로 로그인 → 나의 금융 → 계좌 만들기 → 4자리 계좌 비밀번호 두 번 입력.
3. 신규 계좌번호·0원 잔액 확인 → 계좌 비밀번호 확인 버튼으로 검증.
4. 로그아웃 → staff 로그인 → 별도 직원 화면 진입.
5. 전체 고객 조회 → 검색 → 상세 조회에서 회원 정보·계좌 확인.
6. 직원 계정 관리 → 새 직원 생성 → 다른 직원 활성/비활성 전환.
7. 활동 로그 → 조회·로그인·거부 기록 확인 → JSONL 내려받기.
8. 아래 취약점 실험으로 두 모드의 응답을 비교.

직원은 모든 고객과 직원 계정을 조회·관리할 수 있습니다. 고객은 본인 정보만 조회합니다.
직원 계정에는 가상 계좌를 발급하지 않습니다. 로그인·계좌 비밀번호 원문은 어떤 조회 응답에도 없습니다.
일반 회원가입 요청에 role=staff를 넣어도 고객으로 등록됩니다.
직원 본인 비활성화는 차단하여 최소 한 명의 관리자가 남도록 했습니다.

## 4. 취약점: 고객 상세 조회 BOLA

**공격 흐름:** 고객 로그인 → 고객 상세 조회 API 요청의 고객 번호 변경 → 백엔드가 DB 조회 → 허용하지 않아야 할 고객 정보 반환.
공격자가 DB에 직접 접속하는 구조가 아닙니다. DB 접속 포트는 호스트에 공개하지 않습니다.

대상: `GET /api/customers/{고객번호}`

| 요청자 | 조회 대상 | fixed | vulnerable |
|---|---|---|---|
| 비로그인 | 모든 고객 | 401 | 401 |
| 고객 A | 본인 | 200 | 200 |
| 고객 A | 고객 B | 403 | 200 + 고객 B 정보 |
| 직원 | 모든 고객 | 200 | 200 |
| 고객 A | 직원 관리 API | 403 | 403 |

기본값은 fixed(수정 모드)입니다. 모드 변경은 서버 환경변수로만 가능합니다.
다른 권한 검사나 SQL 처리에는 의도적 취약점을 추가하지 않았습니다.

### 수정 모드 확인
```bash
LAB_MODE=fixed docker compose up -d backend
python3 app/probe.py --expect fixed
```
`normal_status: 200`, `other_customer_status: 403`, `verified: true`가 나와야 합니다.

### 취약 모드 확인
```bash
LAB_MODE=vulnerable docker compose up -d backend
python3 app/probe.py --expect vulnerable
```
`normal_status: 200`, `other_customer_status: 200`, `verified: true`가 나와야 합니다.
컨테이너 재생성 직후 연결 오류가 나면 `docker compose ps`에서 backend가 healthy인지 확인하고 재시도합니다.
probe.py는 기본 시드 데이터와 기본 비밀번호를 사용하는 로컬 서버용입니다.

### 실험 후 복구
```bash
LAB_MODE=fixed docker compose up -d backend
```

Burp 실습은 customer1 로그인 후 로컬 `GET /api/customers/2` 요청을 만들고 `/api/customers/3`으로 변경해 두 모드를 비교하면 됩니다. 로그인 쿠키가 필요합니다.
테스트 스크립트는 정확히 같은 시드 계정·조회 경로를 사용하며 DB를 직접 읽지 않습니다.

## 5. 구성

- web: Nginx, 정적 HTML/CSS/JavaScript, `127.0.0.1:8081`만 공개.
- backend: Flask + SQLAlchemy + Gunicorn, 인증·권한·계좌·로그 API.
- db: PostgreSQL 16, 데이터 전용 내부 네트워크, Docker 볼륨 영속 저장.
- front 네트워크: web ↔ backend. data 내부 네트워크: backend ↔ db.
- 고객 UI와 직원 UI 모두 동일 백엔드 API를 사용.
- 서버 기본 실행은 SQLite로도 가능하지만 Docker 실행 시에는 PostgreSQL을 사용.

파일 안내:
```
app/server.py          DB 모델·API·권한 검사·감사 로그
app/static/index.html 은행 메인·워크스페이스 뼈대
app/static/style.css  데스크톱·모바일 디자인
app/static/app.js     로그인·고객·직원 화면 동작
app/probe.py          로컬 BOLA 비교 시나리오
compose.yaml          웹·백엔드·DB 연결
nginx.conf            정적 파일 및 API 프록시
Dockerfile            백엔드 실행 이미지
tests/test_app.py     API·권한·취약점 테스트
```

## 6. DB 구조

| 테이블 | 주요 저장 정보 |
|---|---|
| users | 아이디·이름·테스트 이메일·비밀번호 해시·역할·활성 상태 |
| accounts | 소유자·가상 계좌번호·계좌 비밀번호 해시·정수 모의 잔액·생성 시각 |
| sessions | 세션 토큰 해시·사용자·CSRF 토큰·만료 시각 |
| events | 요청 ID·시각·사용자·역할·메서드·경로·대상 ID·상태·처리 시간 |
| attempts | 로그인·계좌 비밀번호 검증 실패 횟수 및 제한 시각 |

비밀번호는 Werkzeug scrypt 해시를 사용합니다. 사용자 입력은 ORM 매개변수로 처리합니다.
인증 쿠키는 HttpOnly·SameSite=Strict이며 로컬 HTTP용입니다. 외부 서비스 운영 수준의 배포 구성이 아닙니다.
POST/PATCH는 전용 헤더·동일 Origin·로그인 세션 CSRF 토큰을 검사합니다.
로그인 5분 내 8회 실패, 계좌 비밀번호 5분 내 5회 실패 시 추가 시도를 제한합니다.

## 7. API 요약

| 메서드·주소 | 권한 | 용도 |
|---|---|---|
| POST /api/register | 공개 | 고객 가입 |
| POST /api/login | 공개 | 로그인 |
| GET /api/me | 공개 | 현재 세션 |
| POST /api/logout | 로그인 | 로그아웃 |
| GET /api/accounts | 로그인 | 본인 계좌 |
| POST /api/accounts | 고객 | 계좌 발급 |
| POST /api/accounts/{id}/verify-pin | 소유 고객 | 계좌 비밀번호 검증 |
| GET /api/customers | 직원 | 전체 고객 목록 |
| GET /api/customers/{id} | 본인/직원, 취약 모드 예외 | 고객 상세·계좌 |
| GET/POST /api/staff | 직원 | 직원 목록·생성 |
| PATCH /api/staff/{id} | 직원 | 다른 직원 활성/비활성 |
| GET /api/events | 직원 | 최근 200개 로그 |
| GET /api/events?format=jsonl | 직원 | 최근 200개 로그 내보내기 |
| GET /api/lab | 직원 | 실행 모드 확인 |
| GET /api/health | 공개 | DB 연결 포함 상태 확인 |

비밀번호·PIN·로그인 쿠키·요청 본문은 감사 로그에 저장하지 않습니다.
현재 처리 시간은 백엔드 요청 처리 시간이며 AI 탐지 시간이나 전체 네트워크 지연이 아닙니다.
로그에 공격 정답을 붙이지 않습니다. 별도 평가 프로그램이 실험 실행 기록과 결합해야 합니다.
JSONL 출력은 최근 200개만 포함합니다. 장기 수집은 별도 수집기·페이지네이션 추가가 필요합니다.

## 8. 실행·중지·초기화

중지(데이터 유지):
```bash
docker compose down
```
재시작:
```bash
docker compose up -d
```
DB를 초기화해 테스트 계정부터 다시 시작할 때만 실행 — **이 프로젝트의 가입·계좌·로그가 삭제됩니다**:
```bash
docker compose down -v
docker compose up -d
```
프론트엔드 수정 후 Ctrl+Shift+R로 새로고침. 백엔드 수정 후 `docker compose up -d --build`.
컨테이너 CPU·메모리는 `docker stats`로 확인 가능합니다. 자원 사용량 대시보드는 이번 범위에 포함하지 않았습니다.

## 9. 검증 및 한계

제작 환경에서 자동 API 테스트 8개 통과: 가입 역할 강제·해시 저장, 인증/직원 권한, BOLA 전환, 계좌/PIN, CSRF/Origin, 직원 비활성화·세션 취소, 로그·로그아웃, 로그인 제한.
이 자동 테스트는 SQLite 임시 DB에서 수행했습니다. 별도 로컬 HTTP 서버에서도 probe.py로 수정 모드 403 / 취약 모드 200 응답을 확인했습니다. Compose YAML 구조와 JavaScript 문법 검사도 통과했습니다. 제공된 PostgreSQL Docker 구성은 Docker가 없는 제작 환경에서 실제 기동 검증하지 못했습니다.
브라우저 자동화는 제작 환경의 Chromium 실행 제한으로 완료하지 못했습니다. 사용자 Docker에서 데스크톱·모바일 화면과 버튼 동작의 최종 확인이 필요합니다.

포함하지 않은 기능: 실제 금융 거래, 모의 이체, 이자 계산, 직원 비밀번호 재설정, 회원 탈퇴, 블루 AI, 공격 자동화 에이전트, 자동 평가·재학습.
저축 상품 카드는 디자인 소개이며 준비 중으로 표시합니다.
동시 다중 사용자 부하·동시 계좌 발급 상한 경쟁 조건·대량 로그 보관은 아직 검증하지 않았습니다.

로컬 개발 검증:
```bash
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt pytest
pytest -q tests
python app/server.py
```
이 경우 현재 디렉터리에 a2d-local.db가 만들어지고 8081에서 실행됩니다. Docker와 동시에 같은 포트로 실행하지 마세요.
