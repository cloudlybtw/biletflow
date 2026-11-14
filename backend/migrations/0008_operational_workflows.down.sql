BEGIN;
DROP INDEX support_cases_escalated;
ALTER TABLE support_cases DROP COLUMN escalation_reason, DROP COLUMN escalated_by, DROP COLUMN escalated_at;
DROP TABLE event_reports;
DROP TABLE simulated_payouts;
COMMIT;
