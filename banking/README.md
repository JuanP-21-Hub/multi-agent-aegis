# A2D 은행 통합 실행 안내

팀원의 A2D HTML/CSS 화면을 FinLab FastAPI와 PostgreSQL 17에 연결한 통합 프로젝트입니다.
웹 → Nginx → FastAPI → 기존 5개 테이블로 동작하며 Flask, users, sessions, events DB는 운영하지 않습니다.

- 기준 백엔드: feature/banking-backend @ b73afeeed0a8bb6d6c82f3431de8ddb80b85065e
- 기준 화면: feature/a2d-bank-web @ 11dc0e7eb9b1a21455706c5912e3a9f481b0e0a6
- 통합 브랜치: integration/fastapi-a2d-bank-20261117
- API/DB 비교와 변경 이유: [통합 명세](../docs/INTEGRATION.md)
- 실행 결과와 한계: [검증 기록](../docs/VALIDATION.md)

## 준비

Windows Docker Desktop을 실행하고 WSL2 엔진 및 Ubuntu 연동을 켭니다.
아래 명령은 **Ubuntu 터미널**에서 실행합니다. 신규 설치에는 Git, OpenSSL, Docker Compose v2가 필요합니다.

```bash
docker version
docker compose version
git --version
openssl version
```

## A. 새 DB로 최초 실행

이미 고객/계좌가 저장된 DB를 연결하려면 이 절차 대신 B를 사용하세요.
기존 폴더와 구분되는 새 폴더로 받습니다. 같은 폴더가 있으면 git clone은 중단됩니다.

```bash
cd ~
git clone --single-branch --branch integration/fastapi-a2d-bank-20261117 https://github.com/JuanP-21-Hub/multi-agent-aegis.git aegis-integrated
cd ~/aegis-integrated/banking
bash scripts/init-env.sh
docker compose -p aegis-integrated up -d --build --wait
docker compose -p aegis-integrated ps -a
curl -f http://localhost:8081/api/health/db
docker compose -p aegis-integrated exec backend python -m app.create_staff
```

직원 아이디 예시: staff01 / 이름 예시: 테스트직원.
비밀번호는 실행 중 직접 지정하며 최소 12자입니다. 공통 비밀번호나 자동 생성된 기본 직원은 없습니다.
고객은 화면에서 가입합니다. 예시 입력:

```json
{"login_id":"testuser01","password":"TestPass!1234","full_name":"테스트고객","rrn":"TEST-RRN-123456"}
```

접속: **http://localhost:8081**
로그인 창에서 개인 고객/은행 직원을 구분합니다.
새 계좌는 잔액 0원, 상태 ACTIVE로 표시됩니다.

migrate 컨테이너가 Exited (0)인 것은 정상입니다. 성공 후에만 backend가 시작됩니다.
DB와 backend는 호스트 포트를 열지 않고 Nginx만 127.0.0.1:8081에 연결합니다.

## B. 기존 FastAPI DB를 보존하며 업데이트

대상은 원본 브랜치의 PostgreSQL 17, banklab, bank_admin, bank_data 볼륨입니다.
팀원 Flask용 PostgreSQL 16 볼륨은 이 스키마가 아니므로 연결하지 않습니다.

1. 기존 서버가 실행 중일 때 실제 볼륨 이름을 확인하고 DB를 백업합니다.
2. 원래 사용하던 .env의 **DB_PASSWORD, RRN_ENCRYPTION_KEY, JWT_SECRET를 그대로 사용**합니다.
3. 같은 볼륨을 두 PostgreSQL 프로세스가 동시에 열지 않도록 기존 컨테이너를 중지합니다.
4. 외부 볼륨 설정을 이용해 새 프로젝트를 시작합니다. 볼륨을 찾지 못하면 실패하며 빈 대체 볼륨을 만들지 않습니다.

아래 OLD_BANKING 한 줄은 **기존 .env가 있는 실제 경로**로 수정하세요.
finlab-db / finlab-api는 원본 Compose의 컨테이너 이름입니다. 이름을 바꿨다면 실제 이름을 사용하세요.

```bash
OLD_BANKING="$HOME/multi-agent-aegis/banking"
test -f "$OLD_BANKING/.env"
export BANK_DATA_VOLUME="$(docker inspect finlab-db --format '{{range .Mounts}}{{if eq .Destination "/var/lib/postgresql/data"}}{{.Name}}{{end}}{{end}}')"
test -n "$BANK_DATA_VOLUME"
docker volume inspect "$BANK_DATA_VOLUME"
umask 077
BACKUP_FILE="$HOME/banklab-before-integration-$(date +%Y%m%d-%H%M%S).dump"
docker exec finlab-db pg_dump -U bank_admin -d banklab -Fc > "$BACKUP_FILE"
test -s "$BACKUP_FILE"
cd ~
git clone --single-branch --branch integration/fastapi-a2d-bank-20261117 https://github.com/JuanP-21-Hub/multi-agent-aegis.git aegis-integrated
cd ~/aegis-integrated/banking
test ! -e .env && cp "$OLD_BANKING/.env" .env
chmod 600 .env
printf '\nBANK_DATA_VOLUME=%s\nLAB_MODE=fixed\n' "$BANK_DATA_VOLUME" >> .env
docker stop finlab-api finlab-db
dc() { docker compose -p aegis-integrated -f compose.yaml -f compose.existing.yaml "$@"; }
dc up -d --wait database
dc run --rm migrate
dc up -d --build --wait
dc ps -a
curl -f http://localhost:8081/api/health/db
```

한 줄이 실패하면 이후 명령을 실행하지 말고 원인을 확인하세요.
B 절차에서는 init-env.sh를 실행하지 않습니다. 새 암호화 키로 교체하면 기존 암호문 복호화가 불가능해집니다.
백업은 개인정보를 포함할 수 있으므로 GitHub에 올리지 않습니다.

이미 신규 폴더를 받은 경우 git clone은 건너뛰고 해당 폴더로 이동하세요.
기존 DB의 직원 계정은 그대로 로그인할 수 있으며, 마이그레이션 시 active=true가 됩니다.
필요한 경우 추가 계정:

```bash
dc exec backend python -m app.create_staff
```

이후에도 기존 DB 설치는 항상 같은 두 Compose 파일을 사용합니다. 새 터미널에서:

```bash
cd ~/aegis-integrated/banking
dc() { docker compose -p aegis-integrated -f compose.yaml -f compose.existing.yaml "$@"; }
dc up -d --wait
```

SQL만 별도 적용해야 하는 경우, 백업 후 기존 컨테이너에 다음처럼 적용할 수 있습니다.
새 backend를 먼저 실행하지 마세요.

```bash
docker exec -i finlab-db psql -U bank_admin -d banklab -v ON_ERROR_STOP=1 < database/migrations/001_integration.sql
```

마이그레이션은 트랜잭션과 advisory lock을 사용하고 재실행할 수 있습니다.
DROP, TRUNCATE, 기존 행 UPDATE, 비밀번호 재해시, 암호문 재암호화가 없습니다.
transactions와 계좌 상태는 그대로 유지합니다. 기존 볼륨 삭제나 DB 초기화가 필요하지 않습니다.

## 사용 순서

고객: 회원가입 → 개인 고객 로그인 → 나의 금융 → 계좌 만들기 → 숫자 4자리 입력 → 계좌/PIN 확인.
직원: 은행 직원 로그인 → 전체 고객 조회 → 상세 조회(가상 주민번호 끝 4자리 및 계좌) → 직원 계정 관리 → 활동 로그.
직원 목록에서 본인 계정은 비활성화할 수 없습니다.
직원 비활성화 시 DB의 active 및 token_version 검사로 기존 토큰도 거절하고, 다시 활성화해도 옛 토큰은 살아나지 않습니다.
감사로그 화면/JSONL 다운로드는 최근 200건입니다. API의 before_id/limit로 이전 기록을 조회할 수 있습니다.

로그인 유지 미선택: sessionStorage, 새로고침 유지, 브라우저 탭 세션 종료 시 제거.
선택: localStorage, 브라우저 재실행 유지, 토큰 발급 후 최대 1시간.
자동 재발급은 없습니다. 만료/401은 로그인 상태와 표시 데이터를 제거합니다.
로그아웃은 token_version을 증가시켜 **해당 계정의 모든 기존 JWT를 무효화**합니다.
로그아웃 요청 자체가 네트워크 오류로 실패하면 완료로 표시하지 않고 재시도를 안내합니다.

## BOLA 실습

기본은 fixed입니다. 고객 로그인 후 '접근 권한 실습'에서 다른 테스트 고객 ID를 입력합니다.
같은 GET /api/customers/{customer_id}가 fixed에서는 403, vulnerable에서는 200입니다.
공개되는 데이터는 고객 ID/아이디/이름으로 제한합니다. 계좌/PIN/직원 API에는 실습 우회가 없습니다.

신규 설치 예시:

```bash
LAB_MODE=vulnerable docker compose -p aegis-integrated up -d --force-recreate backend
docker compose -p aegis-integrated up -d --force-recreate web
```

기존 DB 설치에서는 같은 명령에 -f compose.yaml -f compose.existing.yaml을 추가합니다.
실습 후 fixed로 복구:

```bash
LAB_MODE=fixed docker compose -p aegis-integrated up -d --force-recreate backend
docker compose -p aegis-integrated up -d --force-recreate web
```

backend 재생성 후 Nginx도 재생성하여 Docker 내부 IP 변경을 반영합니다.
화면이나 요청 파라미터로 모드를 변경하는 API는 없습니다.
두 모드 모두 로그인 필수, 고객의 직원 API 접근은 403입니다.

## 종료·재시작·문제 확인

신규 설치:

```bash
docker compose -p aegis-integrated stop
docker compose -p aegis-integrated up -d --wait
docker compose -p aegis-integrated logs --tail=100 backend migrate
```

기존 DB 설치는 앞에서 만든 dc 함수를 사용합니다.
정상 종료는 stop으로 충분합니다. down -v는 사용하지 마세요.
8081이 사용 중이면 .env에 WEB_PORT=8082를 추가하고 web을 다시 생성합니다.
실행 설정을 출력하는 docker compose config에는 비밀값이 포함될 수 있으므로 출력 전체를 공유하지 마세요.

## 검증 재실행

실제 사용자 DB 대신 매번 고유한 테스트 프로젝트와 banklab_test DB를 만듭니다.
Ubuntu에 Node 22+, npm, Python 3, OpenSSL, Docker가 필요합니다.
Chromium 설치 단계에서 OS 패키지 설치 권한 및 인터넷이 필요할 수 있습니다.
8081을 사용하는 일반 실행 서버가 있다면 먼저 중지한 후 실행하세요.

```bash
cd ~/aegis-integrated/banking
bash scripts/test-compose.sh
```

테스트는 기존 형식의 고객/계좌/거래/직원 데이터를 넣고 마이그레이션을 2회 적용한 다음,
API 11개 테스트, 프론트 인증 4개 테스트, Nginx 경유 요청, Chromium 화면 조작,
DB/backend/web 재시작 후 데이터 보존을 검증합니다.
테스트 종료 시 테스트 컨테이너만 중지하고 해당 볼륨은 남깁니다.
실제 사용자 DB에 테스트 데이터를 삽입하지 않으며 테스트 코드는 banklab_test 외 DB에서 중단됩니다.

