# 팀원용 A2D 은행 실행 안내

이 폴더는 ATTACK2DEFENSE 캡스톤 가상 은행 **웹사이트/백엔드**입니다. 현재 ARTEX, Blue LLM, Streamlit은 포함되어 있지 않습니다.

## 준비
- Docker Desktop(Windows) 또는 Docker Engine+Docker Compose v2(Linux)
- Windows + Ubuntu WSL 사용자는 Docker Desktop에서 WSL Integration 활성화
- 저장소가 private일 경우 GitHub 접근 권한

## 실행

저장소가 `main`에 반영되어 있다면:

```bash
git clone https://github.com/JuanP-21-Hub/multi-agent-aegis.git
cd multi-agent-aegis/a2d-bank-v2
docker compose up -d --build
```

아직 웹사이트 작업 브랜치만 올라와 있다면:

```bash
git clone --branch feature/a2d-bank-web https://github.com/JuanP-21-Hub/multi-agent-aegis.git
cd multi-agent-aegis/a2d-bank-v2
docker compose up -d --build
```

브라우저: **http://localhost:8081** (실행한 본인 PC에서 열기)

### 기본 실습 계정
| 역할 | ID | Password |
|---|---|---|
| 직원 | `staff` | `DemoBank!2026` |
| 고객 A | `customer1` | `DemoBank!2026` |
| 고객 B | `customer2` | `DemoBank!2026` |

위 값은 공개된 데모 인증정보이므로 **로컬 격리 실습에만 사용**하며 실제 계정/고객정보를 입력하지 마세요.

### 상태 확인 / 종료
```bash
docker compose ps
docker compose logs --tail=60 backend
docker compose down
```

문제가 생기면 `docker compose ps`와 `docker compose logs --tail=60 backend` 출력으로 확인하세요. `docker compose down -v`는 실습 데이터까지 삭제합니다.

### 실습 취약점
기본값 `LAB_MODE=fixed`는 타 고객 조회를 차단합니다. 취약 모드는 로컬 실습용 `LAB_MODE=vulnerable`입니다. 자세한 설명은 [README.md](README.md)를 참고하세요.

## 주의
- 소스코드를 GitHub에 올려도 웹사이트가 인터넷에 배포되는 것은 아닙니다. 실행한 개인 PC의 localhost에서만 접속됩니다.
- PostgreSQL은 Docker 내부 전용 네트워크를 사용합니다. 실서비스 배포를 전제로 만들지 않았습니다.
