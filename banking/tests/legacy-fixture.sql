-- Isolated test database only; deliberately represents data created before migration.
\connect banklab_test
INSERT INTO customers (login_id,password_hash,full_name,rrn_encrypted,rrn_last4)
VALUES ('legacy_probe','preserve-existing-hash','기존고객',decode('010203','hex'),'1234');
INSERT INTO accounts (customer_id,account_number,account_pin_hash,balance,status)
SELECT id,'100-000-000001','preserve-pin-hash',42,'FROZEN' FROM customers WHERE login_id='legacy_probe';
INSERT INTO transactions (account_id,transaction_type,amount,balance_after,description)
SELECT id,'DEPOSIT',42,42,'migration probe' FROM accounts WHERE account_number='100-000-000001';
INSERT INTO staff_users (employee_id,password_hash,display_name,role)
VALUES ('legacy_staff','preserve-staff-hash','기존직원','ADMIN');
