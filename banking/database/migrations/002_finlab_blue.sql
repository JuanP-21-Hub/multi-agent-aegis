BEGIN;
SELECT pg_advisory_xact_lock(20261117);
CREATE TABLE IF NOT EXISTS transfer_requests (
    customer_id BIGINT NOT NULL REFERENCES customers(id),
    request_id UUID NOT NULL,
    source_id BIGINT NOT NULL,
    destination_id BIGINT NOT NULL,
    amount BIGINT NOT NULL CHECK (amount > 0 AND amount <= 1000000),
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (customer_id, request_id),
    CHECK (source_id <> destination_id)
);
COMMIT;
