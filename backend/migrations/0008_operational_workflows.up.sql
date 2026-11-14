BEGIN;
CREATE TABLE simulated_payouts (
 id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
 event_id UUID NOT NULL UNIQUE REFERENCES events(id),
 organizer_user_id UUID NOT NULL REFERENCES users(id),
 amount BIGINT NOT NULL CHECK (amount >= 0),
 status TEXT NOT NULL DEFAULT 'requested' CHECK(status IN ('requested','processing','paid','failed')),
 note TEXT NOT NULL DEFAULT '',
 created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
 updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX simulated_payouts_status ON simulated_payouts(status, created_at);
CREATE TABLE event_reports (
 id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
 event_id UUID NOT NULL REFERENCES events(id),
 reporter_user_id UUID NOT NULL REFERENCES users(id),
 reason TEXT NOT NULL CHECK(length(reason) BETWEEN 1 AND 2000),
 status TEXT NOT NULL DEFAULT 'open' CHECK(status IN ('open','reviewing','resolved','dismissed')),
 resolution TEXT NOT NULL DEFAULT '',
 reviewed_by UUID REFERENCES users(id),
 created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
 updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX event_reports_queue ON event_reports(status, created_at);
ALTER TABLE support_cases ADD COLUMN escalated_at TIMESTAMPTZ,
 ADD COLUMN escalated_by UUID REFERENCES users(id),
 ADD COLUMN escalation_reason TEXT;
CREATE INDEX support_cases_escalated ON support_cases(escalated_at) WHERE escalated_at IS NOT NULL;
COMMIT;
