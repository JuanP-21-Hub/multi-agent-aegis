\connect banklab_test
DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM customers WHERE login_id='legacy_probe' AND password_hash='preserve-existing-hash'
      AND rrn_encrypted=decode('010203','hex') AND rrn_last4='1234' AND token_version=0) THEN
    RAISE EXCEPTION 'Customer data changed';
  END IF;
  IF NOT EXISTS (SELECT 1 FROM accounts WHERE account_number='100-000-000001' AND balance=42
      AND status='FROZEN' AND account_pin_hash='preserve-pin-hash') THEN RAISE EXCEPTION 'Account data changed'; END IF;
  IF NOT EXISTS (SELECT 1 FROM transactions WHERE description='migration probe' AND amount=42) THEN
    RAISE EXCEPTION 'Transaction lost'; END IF;
  IF NOT EXISTS (SELECT 1 FROM staff_users WHERE employee_id='legacy_staff' AND role='ADMIN'
      AND password_hash='preserve-staff-hash' AND active AND token_version=0) THEN RAISE EXCEPTION 'Staff changed'; END IF;
END $$;
