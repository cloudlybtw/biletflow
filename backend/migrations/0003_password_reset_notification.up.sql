-- 12. Password reset email (SRS §4.1)
--
-- ALTER TYPE ... ADD VALUE may run inside a transaction (PG 12+); the new
-- label just can't be used until that transaction commits.

BEGIN;

ALTER TYPE notification_type ADD VALUE 'password_reset';

COMMIT;
