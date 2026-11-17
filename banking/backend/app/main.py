import os
import secrets

import psycopg
from argon2 import PasswordHasher
from cryptography.fernet import Fernet
from fastapi import FastAPI, HTTPException, Request, Query
from pydantic import BaseModel, Field, field_validator


app = FastAPI(
    title="FinLab Banking API",
    version="0.3.0"
)

password_hasher = PasswordHasher()

rrn_cipher = Fernet(
    os.environ["RRN_ENCRYPTION_KEY"].encode()
)


# PostgreSQL 연결 함수
def get_db():
    return psycopg.connect(
        host=os.environ["DB_HOST"],
        port=int(os.getenv("DB_PORT", "5432")),
        dbname=os.environ["DB_NAME"],
        user=os.environ["DB_USER"],
        password=os.environ["DB_PASSWORD"],
        connect_timeout=5
    )


# 회원가입 요청 데이터
class SignupRequest(BaseModel):
    login_id: str = Field(
        min_length=4,
        max_length=50,
        pattern=r"^[a-zA-Z0-9_]+$"
    )
    password: str = Field(min_length=10, max_length=128)
    full_name: str = Field(min_length=1, max_length=100)
    rrn: str = Field(pattern=r"^TEST-RRN-[0-9]{6}$")

    @field_validator("full_name")
    @classmethod
    def validate_name(cls, value):
        value = value.strip()
        if not value:
            raise ValueError("이름을 입력해야 합니다.")
        return value


# 서버 상태 확인
@app.get("/api/health")
def health():
    return {"status": "ok"}


# 데이터베이스 연결 확인
@app.get("/api/health/db")
def database_health():
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT COUNT(*) FROM customers")
                count = cur.fetchone()[0]

        return {
            "status": "ok",
            "database": "connected",
            "customer_count": count
        }

    except psycopg.Error:
        raise HTTPException(
            status_code=503,
            detail="Database connection failed"
        )


# 고객 회원가입
@app.post("/api/customers/signup", status_code=201)
def signup(request: SignupRequest):

    # 로그인 비밀번호 해시
    hashed_password = password_hasher.hash(
        request.password
    )

    # 가상 주민등록번호 암호화
    encrypted_rrn = rrn_cipher.encrypt(
        request.rrn.encode()
    )

    rrn_last4 = request.rrn[-4:]

    try:
        with get_db() as conn:
            with conn.cursor() as cur:

                cur.execute(
                    """
                    INSERT INTO customers
                    (
                        login_id,
                        password_hash,
                        full_name,
                        rrn_encrypted,
                        rrn_last4
                    )
                    VALUES (%s, %s, %s, %s, %s)
                    RETURNING id
                    """,
                    (
                        request.login_id,
                        hashed_password,
                        request.full_name,
                        encrypted_rrn,
                        rrn_last4
                    )
                )

                customer_id = cur.fetchone()[0]

        return {
            "customer_id": customer_id,
            "login_id": request.login_id,
            "full_name": request.full_name,
            "message": "회원가입 완료"
        }

    except psycopg.errors.UniqueViolation:
        raise HTTPException(
            status_code=409,
            detail="이미 사용 중인 아이디입니다."
        )

    except psycopg.Error:
        raise HTTPException(
            status_code=503,
            detail="Database operation failed"
        )

# ============================================
# 고객 로그인 및 JWT 인증
# ============================================

from datetime import datetime, timedelta, timezone

import jwt

from argon2.exceptions import VerificationError, InvalidHashError
from fastapi import Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials


# 로그인 요청 데이터
class LoginRequest(BaseModel):
    login_id: str = Field(min_length=1, max_length=50)
    password: str = Field(min_length=1, max_length=128)


# 로그인 성공 응답 데이터
class LoginResponse(BaseModel):
    access_token: str
    token_type: str
    expires_in: int


# 고객 본인 정보 응답 데이터
class CustomerMeResponse(BaseModel):
    customer_id: int
    login_id: str
    full_name: str


# Bearer 토큰 인증 설정
bearer_scheme = HTTPBearer(auto_error=False)


# 인증 실패 응답
def authentication_error():
    return HTTPException(
        status_code=401,
        detail="인증이 필요하거나 유효하지 않은 토큰입니다.",
        headers={"WWW-Authenticate": "Bearer"}
    )


# JWT 검증 및 로그인 고객 확인
def get_current_customer(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None
    = Depends(bearer_scheme)
):

    if credentials is None:
        raise authentication_error()

    try:
        payload = jwt.decode(
            credentials.credentials,
            os.environ["JWT_SECRET"],
            algorithms=["HS256"],
            issuer="finlab",
            audience="finlab-client",
            options={
                "require": ["sub", "exp", "iss", "aud"]
            }
        )

        if payload.get("role") != "CUSTOMER":
            raise HTTPException(403, "고객 전용 기능입니다.")

        customer_id = int(payload["sub"])

        if customer_id <= 0:
            raise authentication_error()

    except (jwt.InvalidTokenError, ValueError, TypeError):
        raise authentication_error()

    # 토큰에 저장된 고객 ID로 실제 고객 조회
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, login_id, full_name, token_version
                    FROM customers
                    WHERE id = %s
                    """,
                    (customer_id,)
                )

                customer = cur.fetchone()

    except psycopg.Error:
        raise HTTPException(
            status_code=503,
            detail="Database operation failed"
        )

    if customer is None or payload.get("ver", 0) != customer[3]:
        raise authentication_error()

    request.state.actor_type = "CUSTOMER"
    request.state.actor_id = customer_id

    return {
        "customer_id": customer[0],
        "login_id": customer[1],
        "full_name": customer[2]
    }


# ============================================
# 고객 로그인 API
# ============================================

@app.post(
    "/api/auth/customer/login",
    response_model=LoginResponse
)
def customer_login(request: LoginRequest, http_request: Request):

    try:
        with get_db() as conn:
            with conn.cursor() as cur:

                # 로그인 아이디로 고객 검색
                cur.execute(
                    """
                    SELECT id, password_hash, token_version
                    FROM customers
                    WHERE login_id = %s
                    """,
                    (request.login_id,)
                )

                customer = cur.fetchone()

    except psycopg.Error:
        raise HTTPException(
            status_code=503,
            detail="Database operation failed"
        )

    # 존재하지 않는 계정
    if customer is None:
        raise HTTPException(
            status_code=401,
            detail="아이디 또는 비밀번호가 올바르지 않습니다."
        )

    customer_id = customer[0]
    stored_hash = customer[1]

    # 비밀번호 검증
    try:
        password_hasher.verify(
            stored_hash,
            request.password
        )

    except (VerificationError, InvalidHashError):
        raise HTTPException(
            status_code=401,
            detail="아이디 또는 비밀번호가 올바르지 않습니다."
        )

    http_request.state.actor_type = "CUSTOMER"
    http_request.state.actor_id = customer_id

    # 로그인 성공: JWT 토큰 생성
    now = datetime.now(timezone.utc)

    token_payload = {
        "sub": str(customer_id),
        "role": "CUSTOMER",
        "ver": customer[2],
        "iss": "finlab",
        "aud": "finlab-client",
        "iat": now,
        "exp": now + timedelta(hours=1)
    }

    access_token = jwt.encode(
        token_payload,
        os.environ["JWT_SECRET"],
        algorithm="HS256"
    )

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "expires_in": 3600
    }


# ============================================
# 고객 본인 정보 조회 API
# ============================================

@app.get(
    "/api/customers/me",
    response_model=CustomerMeResponse
)
def customer_me(
    customer: dict = Depends(get_current_customer)
):
    return customer

# ============================================
# 계좌 개설 및 계좌 조회
# ============================================

# 계좌 개설 요청 데이터
class CreateAccountRequest(BaseModel):
    account_pin: str = Field(
        min_length=4,
        max_length=4,
        pattern=r"^[0-9]{4}$"
    )


# 계좌 응답 데이터
class AccountResponse(BaseModel):
    account_id: int
    account_number: str
    balance: int
    status: str


# ============================================
# 계좌 개설 API
# ============================================

@app.post(
    "/api/accounts",
    status_code=201,
    response_model=AccountResponse
)
def create_account(
    request: CreateAccountRequest,
    customer: dict = Depends(get_current_customer)
):

    # 로그인한 고객 ID
    customer_id = customer["customer_id"]

    # 계좌 비밀번호 해시
    pin_hash = password_hasher.hash(
        request.account_pin
    )

    try:
        with get_db() as conn:
            with conn.cursor() as cur:

                account = None

                # 계좌번호 중복 발생 시 재시도
                for _ in range(5):

                    # 무작위 9자리 숫자 생성
                    random_number = (
                        f"{secrets.randbelow(1_000_000_000):09d}"
                    )

                    # 가상 은행 계좌번호
                    account_number = (
                        f"100-{random_number[:3]}-"
                        f"{random_number[3:]}"
                    )

                    # accounts 테이블에 계좌 생성
                    cur.execute(
                        """
                        INSERT INTO accounts
                        (
                            customer_id,
                            account_number,
                            account_pin_hash
                        )
                        VALUES (%s, %s, %s)
                        ON CONFLICT (account_number)
                        DO NOTHING
                        RETURNING id, account_number,
                                  balance, status
                        """,
                        (
                            customer_id,
                            account_number,
                            pin_hash
                        )
                    )

                    row = cur.fetchone()

                    if row is not None:
                        account = {
                            "account_id": row[0],
                            "account_number": row[1],
                            "balance": row[2],
                            "status": row[3]
                        }
                        break

                if account is None:
                    raise HTTPException(
                        status_code=503,
                        detail="계좌번호 생성에 실패했습니다."
                    )

        return account

    except psycopg.Error:
        raise HTTPException(
            status_code=503,
            detail="Database operation failed"
        )


# ============================================
# 로그인 고객의 계좌 목록 조회
# ============================================

@app.get(
    "/api/accounts/me",
    response_model=list[AccountResponse]
)
def get_my_accounts(
    customer: dict = Depends(get_current_customer)
):

    customer_id = customer["customer_id"]

    try:
        with get_db() as conn:
            with conn.cursor() as cur:

                cur.execute(
                    """
                    SELECT
                        id,
                        account_number,
                        balance,
                        status
                    FROM accounts
                    WHERE customer_id = %s
                    ORDER BY created_at DESC, id DESC
                    """,
                    (customer_id,)
                )

                rows = cur.fetchall()

        return [
            {
                "account_id": row[0],
                "account_number": row[1],
                "balance": row[2],
                "status": row[3]
            }
            for row in rows
        ]

    except psycopg.Error:
        raise HTTPException(
            status_code=503,
            detail="Database operation failed"
        )


# ============================================
# 직원 로그인 및 고객 조회
# ============================================

class StaffLoginRequest(BaseModel):
    employee_id: str = Field(min_length=1, max_length=50)
    password: str = Field(min_length=1, max_length=128)


class StaffCustomerResponse(BaseModel):
    customer_id: int
    login_id: str
    full_name: str
    rrn_last4: str


# 직원 인증
def get_current_staff(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None
    = Depends(bearer_scheme)
):
    if credentials is None:
        raise authentication_error()

    try:
        payload = jwt.decode(
            credentials.credentials,
            os.environ["JWT_SECRET"],
            algorithms=["HS256"],
            issuer="finlab",
            audience="finlab-client",
            options={
                "require": ["sub", "exp", "iss", "aud"]
            }
        )

        if payload.get("role") not in ("STAFF", "ADMIN"):
            raise HTTPException(403, "직원 전용 기능입니다.")

        staff_id = int(payload["sub"])

        if staff_id <= 0:
            raise authentication_error()

    except (jwt.InvalidTokenError, ValueError, TypeError):
        raise authentication_error()

    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, employee_id, role, active, token_version, display_name
                    FROM staff_users
                    WHERE id = %s
                    """,
                    (staff_id,)
                )
                staff = cur.fetchone()

    except psycopg.Error:
        raise HTTPException(
            status_code=503,
            detail="Database operation failed"
        )

    if (staff is None or staff[2] not in ("STAFF", "ADMIN")
            or not staff[3] or payload.get("ver", 0) != staff[4]):
        raise authentication_error()

    request.state.actor_type = staff[2]
    request.state.actor_id = staff[0]
    return {
        "display_name": staff[5],
        "active": staff[3],
        "staff_id": staff[0],
        "employee_id": staff[1],
        "role": staff[2]
    }


# ============================================
# 직원 로그인 API
# ============================================

@app.post(
    "/api/auth/staff/login",
    response_model=LoginResponse
)
def staff_login(request: StaffLoginRequest, http_request: Request):
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, password_hash, role, active, token_version
                    FROM staff_users
                    WHERE employee_id = %s
                    """,
                    (request.employee_id,)
                )
                staff = cur.fetchone()

    except psycopg.Error:
        raise HTTPException(
            status_code=503,
            detail="Database operation failed"
        )

    login_error = HTTPException(
        status_code=401,
        detail="아이디 또는 비밀번호가 올바르지 않습니다."
    )

    if staff is None or not staff[3] or staff[2] not in ("STAFF", "ADMIN"):
        raise login_error

    try:
        password_hasher.verify(
            staff[1],
            request.password
        )
    except (VerificationError, InvalidHashError):
        raise login_error

    now = datetime.now(timezone.utc)

    http_request.state.actor_type = staff[2]
    http_request.state.actor_id = staff[0]
    payload = {
        "sub": str(staff[0]),
        "ver": staff[4],
        "role": staff[2],
        "iss": "finlab",
        "aud": "finlab-client",
        "iat": now,
        "exp": now + timedelta(hours=1)
    }

    token = jwt.encode(
        payload,
        os.environ["JWT_SECRET"],
        algorithm="HS256"
    )

    return {
        "access_token": token,
        "token_type": "bearer",
        "expires_in": 3600
    }


# ============================================
# 직원용 고객 목록 조회
# ============================================

@app.get(
    "/api/staff/customers",
    response_model=list[StaffCustomerResponse]
)
def staff_customers(
    after_id: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
    staff: dict = Depends(get_current_staff)
):
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, login_id, full_name, rrn_last4
                    FROM customers
                    WHERE id > %s
                    ORDER BY id
                    LIMIT %s
                    """, (after_id, limit)
                )
                rows = cur.fetchall()

    except psycopg.Error:
        raise HTTPException(
            status_code=503,
            detail="Database operation failed"
        )

    return [
        {
            "customer_id": row[0],
            "login_id": row[1],
            "full_name": row[2],
            "rrn_last4": row[3]
        }
        for row in rows
    ]


# ============================================
# 직원용 특정 고객 상세 조회
# ============================================

@app.get(
    "/api/staff/customers/{customer_id}",
    response_model=StaffCustomerResponse
)
def staff_customer_detail(
    customer_id: int,
    staff: dict = Depends(get_current_staff)
):
    try:
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, login_id, full_name, rrn_last4
                    FROM customers
                    WHERE id = %s
                    """,
                    (customer_id,)
                )
                row = cur.fetchone()

    except psycopg.Error:
        raise HTTPException(
            status_code=503,
            detail="Database operation failed"
        )

    if row is None:
        raise HTTPException(
            status_code=404,
            detail="고객을 찾을 수 없습니다."
        )

    return {
        "customer_id": row[0],
        "login_id": row[1],
        "full_name": row[2],
        "rrn_last4": row[3]
    }


# ============================================
# 직원용 고객 계좌 조회
# ============================================

@app.get(
    "/api/staff/customers/{customer_id}/accounts",
    response_model=list[AccountResponse]
)
def staff_customer_accounts(
    customer_id: int,
    staff: dict = Depends(get_current_staff)
):
    try:
        with get_db() as conn:
            with conn.cursor() as cur:

                cur.execute(
                    "SELECT 1 FROM customers WHERE id = %s",
                    (customer_id,)
                )

                if cur.fetchone() is None:
                    raise HTTPException(
                        status_code=404,
                        detail="고객을 찾을 수 없습니다."
                    )

                cur.execute(
                    """
                    SELECT id, account_number, balance, status
                    FROM accounts
                    WHERE customer_id = %s
                    ORDER BY id
                    """,
                    (customer_id,)
                )
                rows = cur.fetchall()

    except psycopg.Error:
        raise HTTPException(
            status_code=503,
            detail="Database operation failed"
        )

    return [
        {
            "account_id": row[0],
            "account_number": row[1],
            "balance": row[2],
            "status": row[3]
        }
        for row in rows
    ]


# Integrated A2D UI APIs and request auditing.
from app.extensions import install
install(app)

