import argparse

from app.main import get_db
from app.transactions import MAX_BALANCE, MAX_TRANSFER


def main():
    parser = argparse.ArgumentParser(description='Docker 운영자용 모의 계좌 자금 준비')
    parser.add_argument('account_id', type=int)
    parser.add_argument('amount', type=int)
    args = parser.parse_args()
    if not 1 <= args.account_id <= MAX_BALANCE or not 1 <= args.amount <= MAX_TRANSFER:
        parser.error('계좌 번호와 금액을 확인하세요. 모의 입금 한도는 100만 원입니다.')
    with get_db() as conn, conn.cursor() as cur:
        cur.execute('''UPDATE accounts SET balance = balance + %s
                       WHERE id = %s AND status = 'ACTIVE' AND balance <= %s
                       RETURNING balance''', (args.amount, args.account_id, MAX_BALANCE - args.amount))
        row = cur.fetchone()
        if not row:
            parser.exit(2, '입금 가능한 모의 계좌를 찾을 수 없습니다.\n')
        cur.execute('''INSERT INTO transactions (account_id, transaction_type, amount, balance_after, description)
                       VALUES (%s, 'DEPOSIT', %s, %s, '모의 실습 잔액')''', (args.account_id, args.amount, row[0]))
    print('모의 실습 잔액을 준비했습니다.')


if __name__ == '__main__':
    main()
