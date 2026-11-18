
import argparse
import getpass

from app.main import get_db, password_hasher


def main():
    parser = argparse.ArgumentParser(description="로컬 은행 직원 계정 생성")
    parser.add_argument("--role", choices=("STAFF", "ADMIN"), default="STAFF")
    role = parser.parse_args().role
    employee_id = input("직원 아이디: ").strip()
    display_name = input("직원 이름: ").strip()

    password = getpass.getpass("직원 비밀번호: ")
    password_confirm = getpass.getpass("비밀번호 확인: ")

    if not employee_id or not display_name:
        print("아이디와 이름을 입력해야 합니다.")
        return

    if len(password) < 12:
        print("비밀번호는 최소 12자리로 설정하세요.")
        return

    if password != password_confirm:
        print("비밀번호가 일치하지 않습니다.")
        return

    hashed_password = password_hasher.hash(password)

    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO staff_users
                (employee_id, password_hash, display_name, role)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (employee_id) DO NOTHING
                RETURNING id
                """,
                (employee_id, hashed_password, display_name, role)
            )
            result = cur.fetchone()

    if result is None:
        print("이미 존재하는 직원 아이디입니다.")
    else:
        print(f"직원 계정 생성 완료! ID: {result[0]}")


if __name__ == "__main__":
    main()
