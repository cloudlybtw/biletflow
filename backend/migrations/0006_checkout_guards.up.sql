BEGIN;
-- One live payment attempt per order, and one issued ticket per attendee.
CREATE UNIQUE INDEX uq_payments_initiated_ticket_order ON payments (order_id)
    WHERE purpose = 'ticket_purchase' AND status = 'initiated';
CREATE UNIQUE INDEX uq_tickets_attendee ON tickets (attendee_id);
COMMIT;
