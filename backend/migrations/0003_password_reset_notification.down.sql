BEGIN;

-- Postgres can't drop an enum label: rebuild the type without it.
DELETE FROM notifications WHERE type = 'password_reset';

ALTER TYPE notification_type RENAME TO notification_type_old;

CREATE TYPE notification_type AS ENUM ('account_verification', 'order_confirmation',
                                       'payment_failed', 'ticket_delivery', 'event_update',
                                       'event_cancelled', 'refund_completed', 'payout_status',
                                       'support_new_message', 'support_assigned',
                                       'support_status_changed');

ALTER TABLE notifications
    ALTER COLUMN type TYPE notification_type USING type::text::notification_type;

DROP TYPE notification_type_old;

COMMIT;
