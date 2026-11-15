
# FinLab Banking Backend

가상 금융 서비스의 FastAPI 백엔드 및 PostgreSQL 데이터베이스.

## 실행 환경

- Docker Desktop (WSL2)
- Ubuntu
- Docker Compose

## 최초 실행 방법

Ubuntu 터미널에서 프로젝트 폴더로 이동.

```bash
cd multi-agent-aegis/banking
```

최초 실행 시 환경변수 파일을 생성.

```bash
echo "DB_PASSWORD=$(openssl rand -hex 24)" > .env
echo "RRN_ENCRYPTION_KEY=$(openssl rand -base64 32 | tr '+/' '-_')" >> .env
echo "JWT_SECRET=$(openssl rand -hex 32)" >> .env
chmod 600 .env
```

Docker 컨테이너를 실행.

```bash
docker compose up -d --build
```

처음 실행하면 PostgreSQL에 빈 테이블 5개가 자동 생성.

## API 테스트

- API 문서: http://localhost:8000/docs
- 서버 확인: http://localhost:8000/api/health
- DB 연결 확인: http://localhost:8000/api/health/db

## 직원 계정 생성

```bash
docker compose exec backend python -m app.create_staff
```

직원 아이디, 이름, 비밀번호를 입력하여 직원 계정을 생성.

## 종료

```bash
docker compose stop
```

## 주의사항

- 초기 고객 및 계좌 데이터는 포함되어 있지 않음.
- 고객은 회원가입 API를 통해 생성함.
- `.env` 파일은 GitHub에 업로드하지 않음.
- Docker 데이터 볼륨을 삭제하면 저장된 데이터도 사라질 수 있음.
