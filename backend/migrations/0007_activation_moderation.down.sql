BEGIN;
DROP INDEX uq_payments_live_activation;
DROP INDEX ix_payments_activation;
ALTER TABLE payments DROP CONSTRAINT payments_activation_target;
ALTER TABLE payments DROP COLUMN activation_id;
ALTER TABLE events
    DROP COLUMN suspension_reason,
    DROP COLUMN suspended_by,
    DROP COLUMN suspended_at,
    DROP COLUMN is_suspended;
COMMIT;
