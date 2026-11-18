"""Customer-owned transaction history and simulated transfers."""

from uuid import UUID, uuid4

from fastapi import Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field
from psycopg.rows import dict_row

MAX_BALANCE = 2**63 - 1
MAX_TRANSFER = 1_000_000


class TransferRequest(BaseModel):
    from_account: int = Field(gt=0, le=MAX_BALANCE, strict=True)
    to_account: int = Field(gt=0, le=MAX_BALANCE, strict=True)
    amount: int = Field(gt=0, le=MAX_TRANSFER, strict=True)
    account_pin: str = Field(pattern=r"^[0-9]{4}$")
    request_id: UUID = Field(default_factory=uuid4)


def install_transactions(app, core):
    def current_owner(request: Request, credentials=Depends(core.bearer_scheme)):
        request.state.required_role = 'ACCOUNT_OWNER'
        return core.get_current_customer(request, credentials)

    @app.get('/api/accounts/{account_id}/transactions')
    def account_transactions(
        account_id: int, request: Request,
        limit: int = Query(100, ge=1, le=200),
        customer: dict = Depends(current_owner),
    ):
        with core.get_db() as conn, conn.cursor(row_factory=dict_row) as cur:
            cur.execute('SELECT 1 FROM accounts WHERE id = %s AND customer_id = %s',
                        (account_id, customer['customer_id']))
            if cur.fetchone() is None:
                raise HTTPException(403, '계좌에 접근할 수 없습니다.')
            request.state.owner_decision = 'allowed'
            cur.execute('''SELECT id, transaction_type, amount, balance_after, description, created_at
                           FROM transactions WHERE account_id = %s ORDER BY id DESC LIMIT %s''',
                        (account_id, limit))
            return {'items': cur.fetchall()}

    @app.post('/api/transfers', status_code=201)
    def transfer(body: TransferRequest, request: Request, customer: dict = Depends(current_owner)):
        if body.from_account == body.to_account:
            raise HTTPException(422, '출금 계좌와 입금 계좌는 달라야 합니다.')
        customer_id = customer['customer_id']
        with core.get_db() as conn, conn.cursor(row_factory=dict_row) as cur:
            cur.execute('''SELECT id, customer_id, balance, status, account_pin_hash
                           FROM accounts WHERE id IN (%s, %s)
                           ORDER BY id FOR NO KEY UPDATE''', (body.from_account, body.to_account))
            accounts = {row['id']: row for row in cur.fetchall()}
            source = accounts.get(body.from_account)
            if source is None or source['customer_id'] != customer_id:
                raise HTTPException(403, '출금 계좌에 접근할 수 없습니다.')
            try:
                core.password_hasher.verify(source['account_pin_hash'], body.account_pin)
            except (core.VerificationError, core.InvalidHashError):
                raise HTTPException(403, '계좌 비밀번호가 일치하지 않습니다.')
            request.state.owner_decision = 'allowed'

            cur.execute('''INSERT INTO transfer_requests (customer_id, request_id, source_id, destination_id, amount)
                           VALUES (%s, %s, %s, %s, %s)
                           ON CONFLICT (customer_id, request_id) DO NOTHING
                           RETURNING request_id''',
                        (customer_id, body.request_id, body.from_account, body.to_account, body.amount))
            if cur.fetchone() is None:
                cur.execute('''SELECT source_id, destination_id, amount FROM transfer_requests
                               WHERE customer_id = %s AND request_id = %s''',
                            (customer_id, body.request_id))
                prior = cur.fetchone()
                if (prior['source_id'], prior['destination_id'], prior['amount']) != (
                    body.from_account, body.to_account, body.amount
                ):
                    raise HTTPException(409, '같은 요청 ID에 다른 이체 정보가 등록돼 있습니다.')
                return {'request_id': body.request_id, 'amount': body.amount}

            destination = accounts.get(body.to_account)
            if not destination or destination['status'] != 'ACTIVE' or source['status'] != 'ACTIVE':
                raise HTTPException(409, '이체할 수 있는 계좌 상태인지 확인해 주세요.')
            if source['balance'] < body.amount or destination['balance'] > MAX_BALANCE - body.amount:
                raise HTTPException(409, '계좌 잔액 한도로 이체할 수 없습니다.')

            for account, change in ((source, -body.amount), (destination, body.amount)):
                balance = account['balance'] + change
                cur.execute('UPDATE accounts SET balance = %s WHERE id = %s', (balance, account['id']))
                cur.execute('''INSERT INTO transactions (account_id, transaction_type, amount, balance_after, description)
                               VALUES (%s, 'TRANSFER', %s, %s, %s)''',
                            (account['id'], body.amount, balance, '모의 송금' if change < 0 else '모의 입금'))
        return {'request_id': body.request_id, 'amount': body.amount}
