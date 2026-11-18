# A2D 은행 · FinLab Blue 통합

A2D 은행의 Nginx 화면, FastAPI와 PostgreSQL은 Docker Desktop에서 실행합니다. PowerShell에서 은행의 감사 로그를 읽고, Runpod의 gpt-oss-20b로 분석합니다. 실행마다 브라우저에서 열 수 있는 HTML 보고서와 Streamlit 결과 JSON이 저장됩니다.

## 1. 팀원 실행 방법

### 이 PC에서 은행을 이미 실행한 경우

기존 은행 폴더의 설정 파일, 암호화 키, Compose 프로젝트 이름과 DB 볼륨을 사용합니다. 기존 Windows 시작 파일로 은행을 띄웠다면 같은 작업 폴더에서 새 코드를 적용하고, 이전 시작 명령에 사용한 프로젝트 이름과 설정 파일을 아래 명령에도 지정합니다.

~~~powershell
cd .\banking
docker compose ls
$Project = Read-Host '기존 은행 Compose 프로젝트 이름'
python .\lab.py -p $Project start
~~~

기존 명령에 환경 파일 또는 추가 Compose 파일이 있었다면 동일하게 전달합니다. 아래 예는 외부에 이미 있는 DB 볼륨을 쓰는 경우입니다.

~~~powershell
python .\lab.py -p $Project --env-file .\.env -f .\compose.existing.yaml start
~~~

위에 지정한 옵션은 이후 로그 조회, 분석, 중지에도 동일하게 사용합니다. 외부 볼륨을 쓰는 경우 기존 설정의 BANK_DATA_VOLUME 이름과 DB 암호화 키를 보존하세요.

### 팀원이 처음 실행하는 경우

Docker Desktop과 Python 3.12 이상을 설치합니다. WSL2 Ubuntu에서 Docker Desktop 연동과 Git을 설정하고, 아래 명령으로 처음 쓸 은행 설정을 준비합니다.

~~~bash
git clone --single-branch --branch integration/finlab-blue-rebuild https://github.com/JuanP-21-Hub/multi-agent-aegis.git
cd multi-agent-aegis/banking
bash scripts/init-env.sh
~~~

Windows 탐색기로 같은 banking 폴더를 열고, 주소창에서 powershell을 실행합니다. Python이 PATH에 없다면 아래의 python 대신 설치된 python.exe를 사용합니다.

~~~powershell
python .\lab.py start
Invoke-RestMethod http://127.0.0.1:8081/api/health/db
~~~

banking 폴더가 WSL의 Linux 파일 시스템에 있다면 설정 생성과 은행 시작을 같은 WSL 또는 Docker Desktop 파일 공유 환경에서 진행하세요. 기본 은행 주소는 http://127.0.0.1:8081입니다. .env에 WEB_PORT가 설정된 환경에서는 그 포트를 사용합니다.

## 2. 테스트 계정과 은행 사용

- 고객은 은행 화면에서 가상 주민번호 형식으로 가입하고, 로그인한 뒤 모의 계좌를 만듭니다.
- 직원과 관리자는 같은 Compose 프로젝트의 백엔드 컨테이너에서 생성합니다. 기존 프로젝트에 -p 옵션을 썼다면 아래 명령에도 붙입니다. 비밀번호는 실행 중에 직접 입력합니다.

~~~powershell
docker compose exec backend python -m app.create_staff
docker compose exec backend python -m app.create_staff --role ADMIN
~~~

직원 화면의 **활동 로그**는 요청과 권한 검사 결과를 보여줍니다. 관리자에게는 역할이 요구된 요청만 모아 보는 **보안 기록** 메뉴도 표시됩니다. 고객 화면에서는 본인 계좌만 거래 내역을 확인하고, 계좌 비밀번호를 입력해 모의 이체를 할 수 있습니다. 기존 잔액이 0원인 테스트 계좌는 Docker 운영자가 아래처럼 모의 자금을 준비한 뒤 이체를 확인합니다.

~~~powershell
docker compose exec backend python -m app.fund_demo 1 10000
~~~

위 명령의 1은 테스트 화면에 표시되는 출금 계좌 ID입니다. 이체는 잔액과 양쪽 거래 기록을 한 DB 트랜잭션으로 저장합니다. 동일한 요청 ID와 이체 내용을 재전송하면 이전 결과를 반환합니다.

## 3. Runpod 연결

Runpod Pod에서 vLLM으로 openai/gpt-oss-20b를 Pod 내부의 127.0.0.1:8000에 실행합니다. Pod에 접속하는 PowerShell에서 SSH 포트 포워딩 옵션을 추가합니다. HOST와 PORT는 Runpod의 Direct TCP ports에 표시된 값으로 바꿉니다.

~~~powershell
ssh -i "$env:USERPROFILE\.ssh\id_ed25519" -p PORT -L 127.0.0.1:18000:127.0.0.1:8000 root@HOST
~~~

새 Pod라면 SSH로 접속한 Linux 터미널에서 모델 서버를 준비합니다. 앞서 사용한 RTX A5000 테스트는 vLLM 0.34.0, 컨텍스트 8,192토큰, 동시 요청 1개로 구동했습니다.

~~~bash
uv venv /opt/finlab-vllm/venv
uv pip install --python /opt/finlab-vllm/venv/bin/python 'vllm==0.34.0' --torch-backend=auto
/opt/finlab-vllm/venv/bin/vllm serve openai/gpt-oss-20b --host 127.0.0.1 --port 8000 --max-model-len 8192 --max-num-seqs 1 --enforce-eager
~~~

SSH 창을 켜 둔 채, **banking 폴더를 연 별도의 Windows PowerShell**에서 실행합니다.

~~~powershell
(Invoke-RestMethod http://127.0.0.1:18000/v1/models).data.id
$env:FINLAB_BLUE_BASE_URL = 'http://127.0.0.1:18000/v1'
$env:FINLAB_BLUE_MODEL = 'openai/gpt-oss-20b'
~~~

## 4. 시연 순서와 결과 확인

1. 은행 화면에서 정상 테스트 로그인, 계좌 조회 또는 직원 조회를 진행합니다.
2. 아래 순서대로 감사 로그를 확인하고 Blue 분석을 실행합니다. 기존 Compose 옵션을 쓰는 PC에서는 동일한 옵션을 logs와 run 앞에 넣습니다.

~~~powershell
python .\lab.py logs
Get-Content .\logs\security.jsonl -Tail 10
python .\lab.py run
explorer .\logs
~~~

- 기본 run은 Docker 은행의 최근 감사 로그를 읽고, 모델 ID와 묶음별 판정을 PowerShell에 출력합니다. HTML은 logs/report_실행번호.html에 생성됩니다. 보고서에는 권한 정책 대조, Blue 판정과 권고, 실제 역할·필요 역할·판정이 담긴 근거 로그가 나옵니다.
- 보유한 감사 로그는 python .\lab.py run --log 경로 로 읽을 수 있습니다.
- python .\lab.py run --scenario staff_access 는 저장된 합성 로그로 직원 역할 판정의 예시를 재생하며, 보고서에 합성 데이터가 표시됩니다. 기본 검사만 확인할 때는 --baseline-only 를 붙입니다.
- 런타임 모델 입력은 요청 메서드, 경로 템플릿, 상태, 역할, 권한 판정 등 정규화된 감사 항목입니다. DB 내 사용자 식별자와 HTTP 본문은 전송 범위에서 제외됩니다.

### Streamlit에서 같은 실행 확인

~~~powershell
cd .\blue\dashboard
python -m pip install -r requirements.txt
python -m streamlit run app.py --server.address 127.0.0.1
~~~

http://127.0.0.1:8501에서 **실제 결과 파일**을 고른 다음 해당 실행을 선택합니다. 결과 JSON은 blue/dashboard/runs/실행번호/evaluation.json에 저장됩니다. 탐지 비교, 대응 권고, 근거 및 평가 탭에서 같은 실행을 볼 수 있습니다.

## 5. 중지와 기존 데이터

~~~powershell
python .\lab.py stop
~~~

기존 Compose 옵션을 사용한 경우 중지 명령에도 붙이세요. 중지는 컨테이너를 정지하고 DB 볼륨을 보존합니다. 기존 DB를 다른 PC로 옮길 경우 먼저 백업하고, 원래 .env와 암호화 키로 기존 볼륨을 연결한 다음 마이그레이션을 적용합니다. 002_finlab_blue.sql은 이체 요청 기록 테이블을 추가합니다.

## 6. 검증 범위

합성 로그의 기본 검사와 모의 모델 응답으로 JSON·HTML 생성 및 로그 필터를 검증합니다. 운영 환경에서는 DB 연결 확인, 테스트 로그인·조회, Runpod 모델 ID, HTML의 로그 행을 순서대로 확인하세요.
