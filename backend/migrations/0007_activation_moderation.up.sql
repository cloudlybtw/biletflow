BEGIN;

ALTER TABLE events
    ADD COLUMN is_suspended BOOLEAN NOT NULL DEFAULT false,
    ADD COLUMN suspended_at TIMESTAMPTZ,
    ADD COLUMN suspended_by UUID REFERENCES users(id) ON DELETE SET NULL,
    ADD COLUMN suspension_reason TEXT;

ALTER TABLE payments ADD COLUMN activation_id UUID REFERENCES paid_sales_activations(id) ON DELETE RESTRICT;
ALTER TABLE payments ADD CONSTRAINT payments_activation_target CHECK (
    (purpose = 'activation_fee' AND activation_id IS NOT NULL AND order_id IS NULL)
    OR (purpose = 'ticket_purchase' AND activation_id IS NULL)
);
CREATE INDEX ix_payments_activation ON payments (activation_id);
CREATE UNIQUE INDEX uq_payments_live_activation ON payments (activation_id)
    WHERE purpose = 'activation_fee' AND status IN ('initiated', 'succeeded');

COMMIT;
