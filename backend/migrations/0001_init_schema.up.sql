BEGIN;

CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE EXTENSION IF NOT EXISTS citext;

-- Shared helpers

CREATE FUNCTION set_updated_at() RETURNS trigger AS $$
BEGIN
    NEW.updated_at := now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE FUNCTION prevent_mutation() RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION 'table % is append-only (attempted %)', TG_TABLE_NAME, TG_OP;
END;
$$ LANGUAGE plpgsql;

-- Enumerated types

CREATE TYPE platform_role         AS ENUM ('attendee', 'platform_admin');
CREATE TYPE user_status           AS ENUM ('active', 'suspended', 'deleted');
CREATE TYPE verification_status   AS ENUM ('unverified', 'pending', 'verified', 'rejected');
CREATE TYPE payout_account_status AS ENUM ('pending', 'active', 'disabled');
CREATE TYPE staff_role            AS ENUM ('event_admin', 'support_agent', 'co_organizer');

CREATE TYPE event_visibility      AS ENUM ('public', 'unlisted', 'private');
CREATE TYPE event_status          AS ENUM ('draft', 'published', 'unpublished', 'cancelled');
CREATE TYPE seating_mode          AS ENUM ('general_admission', 'assigned');
CREATE TYPE paid_sales_status     AS ENUM ('disabled', 'pending', 'active', 'suspended');
CREATE TYPE activation_status     AS ENUM ('pending', 'active', 'suspended');

CREATE TYPE seat_hold_status      AS ENUM ('active', 'converted', 'released', 'expired');

CREATE TYPE order_status          AS ENUM ('pending', 'awaiting_payment', 'paid', 'completed',
                                           'cancelled', 'refunded', 'partially_refunded', 'expired');
CREATE TYPE payment_purpose       AS ENUM ('ticket_purchase', 'activation_fee');
CREATE TYPE payment_status        AS ENUM ('initiated', 'succeeded', 'failed', 'cancelled');
CREATE TYPE refund_status         AS ENUM ('requested', 'processing', 'completed', 'failed');

CREATE TYPE ticket_status         AS ENUM ('valid', 'checked_in', 'cancelled', 'refunded');
CREATE TYPE check_in_action       AS ENUM ('check_in', 'reverse');
CREATE TYPE check_in_result       AS ENUM ('valid', 'duplicate', 'cancelled', 'refunded',
                                           'invalid', 'wrong_event', 'campaign_code_rejected');
CREATE TYPE check_in_source       AS ENUM ('qr_scan', 'manual_search');

CREATE TYPE discount_type         AS ENUM ('percent', 'fixed');
CREATE TYPE campaign_status       AS ENUM ('draft', 'active', 'disabled', 'expired');

CREATE TYPE support_case_type     AS ENUM ('attendee', 'organizer');
CREATE TYPE support_category      AS ENUM ('ticket_delivery', 'payment', 'refund', 'seating',
                                           'event_information', 'check_in', 'account', 'technical');
CREATE TYPE support_status        AS ENUM ('open', 'in_progress', 'waiting_for_customer', 'resolved');
CREATE TYPE support_sender_role   AS ENUM ('requester', 'staff');

CREATE TYPE notification_channel  AS ENUM ('email', 'in_app');
CREATE TYPE notification_status   AS ENUM ('queued', 'sent', 'failed', 'read');
CREATE TYPE notification_type     AS ENUM ('account_verification', 'order_confirmation',
                                           'payment_failed', 'ticket_delivery', 'event_update',
                                           'event_cancelled', 'refund_completed', 'payout_status',
                                           'support_new_message', 'support_assigned',
                                           'support_status_changed');

-- 1. Identity and access

CREATE TABLE users (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email             CITEXT      NOT NULL UNIQUE,
    password_hash     TEXT        NOT NULL,
    full_name         TEXT        NOT NULL,
    phone             TEXT,
    locale            TEXT        NOT NULL DEFAULT 'ru' CHECK (locale IN ('kk', 'ru', 'en')), -- not in erd
    platform_role     platform_role NOT NULL DEFAULT 'attendee',
    status            user_status NOT NULL DEFAULT 'active',
    email_verified_at TIMESTAMPTZ,
    last_login_at     TIMESTAMPTZ,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE organizer_profiles (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id             UUID NOT NULL UNIQUE REFERENCES users(id) ON DELETE CASCADE,
    display_name        TEXT NOT NULL,
    contact_email       CITEXT NOT NULL,
    contact_phone       TEXT,
    description         TEXT,
    verification_status verification_status NOT NULL DEFAULT 'unverified',
    verified_at         TIMESTAMPTZ,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE payout_accounts (
    id                   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organizer_profile_id UUID NOT NULL REFERENCES organizer_profiles(id) ON DELETE CASCADE,
    provider             TEXT NOT NULL,
    external_account_ref TEXT NOT NULL,
    account_holder_name  TEXT NOT NULL,
    currency             CHAR(3) NOT NULL DEFAULT 'KZT',
    status               payout_account_status NOT NULL DEFAULT 'pending',
    is_default           BOOLEAN NOT NULL DEFAULT false,
    is_simulated         BOOLEAN NOT NULL DEFAULT true,
    created_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (provider, external_account_ref)
);

CREATE UNIQUE INDEX uq_payout_accounts_default
    ON payout_accounts (organizer_profile_id) WHERE is_default;

-- 2. Venues and seating

CREATE TABLE venues (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name          TEXT NOT NULL,
    address_line  TEXT NOT NULL,
    city          TEXT NOT NULL,
    country       CHAR(2) NOT NULL DEFAULT 'KZ',
    latitude      NUMERIC(9,6),
    longitude     NUMERIC(9,6),
    timezone      TEXT NOT NULL DEFAULT 'Asia/Almaty',
    is_predefined BOOLEAN NOT NULL DEFAULT false,
    created_by    UUID REFERENCES users(id) ON DELETE SET NULL,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE price_categories (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    venue_id      UUID NOT NULL REFERENCES venues(id) ON DELETE CASCADE,
    code          TEXT NOT NULL,
    name          TEXT NOT NULL,
    display_color TEXT,
    UNIQUE (venue_id, code)
);

CREATE TABLE venue_sections (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    venue_id      UUID NOT NULL REFERENCES venues(id) ON DELETE CASCADE,
    name          TEXT NOT NULL,
    display_order INTEGER NOT NULL DEFAULT 0,
    UNIQUE (venue_id, name)
);

CREATE TABLE venue_rows (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    section_id    UUID NOT NULL REFERENCES venue_sections(id) ON DELETE CASCADE,
    label         TEXT NOT NULL,
    display_order INTEGER NOT NULL DEFAULT 0,
    UNIQUE (section_id, label)
);

CREATE TABLE seats (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    row_id            UUID NOT NULL REFERENCES venue_rows(id) ON DELETE CASCADE,
    price_category_id UUID REFERENCES price_categories(id) ON DELETE SET NULL,
    seat_number       TEXT NOT NULL,
    is_accessible     BOOLEAN NOT NULL DEFAULT false,
    position_x        NUMERIC(8,2) NOT NULL,
    position_y        NUMERIC(8,2) NOT NULL,
    UNIQUE (row_id, seat_number)
);

-- 3. Events

CREATE TABLE event_categories (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    slug          TEXT NOT NULL UNIQUE,
    name_kk       TEXT NOT NULL,
    name_ru       TEXT NOT NULL,
    name_en       TEXT NOT NULL,
    display_order INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE events (
    id                     UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    organizer_profile_id   UUID NOT NULL REFERENCES organizer_profiles(id) ON DELETE RESTRICT,
    venue_id               UUID REFERENCES venues(id) ON DELETE RESTRICT,
    category_id            UUID REFERENCES event_categories(id) ON DELETE SET NULL,
    title                  TEXT NOT NULL,
    slug                   TEXT NOT NULL UNIQUE,
    description            TEXT,
    timezone               TEXT NOT NULL DEFAULT 'Asia/Almaty',
    starts_at              TIMESTAMPTZ NOT NULL,
    ends_at                TIMESTAMPTZ NOT NULL,
    visibility             event_visibility  NOT NULL DEFAULT 'public',
    status                 event_status      NOT NULL DEFAULT 'draft',
    seating_mode           seating_mode      NOT NULL DEFAULT 'general_admission',
    paid_sales_status      paid_sales_status NOT NULL DEFAULT 'disabled',
    capacity               INTEGER CHECK (capacity IS NULL OR capacity > 0),
    registration_opens_at  TIMESTAMPTZ,
    registration_closes_at TIMESTAMPTZ,
    refund_policy          TEXT,
    ics_uid                TEXT NOT NULL UNIQUE DEFAULT (gen_random_uuid()::text || '@biletflow.kz'),
    ics_sequence           INTEGER NOT NULL DEFAULT 0,
    published_at           TIMESTAMPTZ,
    cancelled_at           TIMESTAMPTZ,
    created_at             TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at             TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT events_time_order CHECK (ends_at > starts_at),
    CONSTRAINT events_registration_window CHECK (
        registration_opens_at IS NULL OR registration_closes_at IS NULL
        OR registration_closes_at > registration_opens_at),
    CONSTRAINT events_assigned_needs_venue CHECK (
        seating_mode = 'general_admission' OR venue_id IS NOT NULL)
);

CREATE INDEX ix_events_organizer     ON events (organizer_profile_id, starts_at DESC);
CREATE INDEX ix_events_status_starts ON events (status, starts_at);
CREATE INDEX ix_events_public_browse ON events (starts_at)
    WHERE status = 'published' AND visibility = 'public';

CREATE TABLE event_images (
    id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_id   UUID NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    url        TEXT NOT NULL,
    alt_text   TEXT,
    sort_order INTEGER NOT NULL DEFAULT 0,
    is_cover   BOOLEAN NOT NULL DEFAULT false
);
CREATE UNIQUE INDEX uq_event_images_cover ON event_images (event_id) WHERE is_cover;

CREATE TABLE staff_assignments (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_id    UUID NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    user_id     UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    role        staff_role NOT NULL,
    assigned_by UUID REFERENCES users(id) ON DELETE SET NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now(),
    revoked_at  TIMESTAMPTZ
);
CREATE UNIQUE INDEX uq_staff_assignments_active
    ON staff_assignments (event_id, user_id, role) WHERE revoked_at IS NULL;
CREATE INDEX ix_staff_assignments_user ON staff_assignments (user_id) WHERE revoked_at IS NULL;

-- 4. Ticket inventory and seat holds

CREATE TABLE ticket_types (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_id          UUID NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    name              TEXT NOT NULL,
    description       TEXT,
    price_amount      BIGINT NOT NULL DEFAULT 0 CHECK (price_amount >= 0),
    currency          CHAR(3) NOT NULL DEFAULT 'KZT',
    quantity_total    INTEGER NOT NULL CHECK (quantity_total >= 0),
    quantity_reserved INTEGER NOT NULL DEFAULT 0 CHECK (quantity_reserved >= 0),
    quantity_sold     INTEGER NOT NULL DEFAULT 0 CHECK (quantity_sold >= 0),
    min_per_order     INTEGER NOT NULL DEFAULT 1 CHECK (min_per_order >= 1),
    max_per_order     INTEGER NOT NULL DEFAULT 10,
    sales_start_at    TIMESTAMPTZ,
    sales_end_at      TIMESTAMPTZ,
    is_hidden         BOOLEAN NOT NULL DEFAULT false,
    display_order     INTEGER NOT NULL DEFAULT 0,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at        TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (event_id, name),
    CONSTRAINT ticket_types_order_limits CHECK (max_per_order >= min_per_order),
    CONSTRAINT ticket_types_sales_window CHECK (
        sales_start_at IS NULL OR sales_end_at IS NULL OR sales_end_at > sales_start_at),
    CONSTRAINT ticket_types_not_oversold CHECK (
        quantity_reserved + quantity_sold <= quantity_total)
);

CREATE TABLE event_price_category_ticket_types (
    event_id          UUID NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    price_category_id UUID NOT NULL REFERENCES price_categories(id) ON DELETE CASCADE,
    ticket_type_id    UUID NOT NULL REFERENCES ticket_types(id) ON DELETE CASCADE,
    PRIMARY KEY (event_id, price_category_id)
);

CREATE TABLE seat_holds (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_id        UUID NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    seat_id         UUID NOT NULL REFERENCES seats(id) ON DELETE CASCADE,
    ticket_type_id  UUID NOT NULL REFERENCES ticket_types(id) ON DELETE CASCADE,
    held_by_user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    session_token   TEXT NOT NULL,
    order_id        UUID,
    status          seat_hold_status NOT NULL DEFAULT 'active',
    expires_at      TIMESTAMPTZ NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX uq_seat_holds_active_seat
    ON seat_holds (event_id, seat_id) WHERE status = 'active';
CREATE INDEX ix_seat_holds_expiry ON seat_holds (expires_at) WHERE status = 'active';

-- 5. Promotions

CREATE TABLE campaigns (
    id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_id         UUID NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    name             TEXT NOT NULL,
    discount_type    discount_type NOT NULL,
    discount_value   BIGINT NOT NULL CHECK (discount_value > 0),
    currency         CHAR(3) NOT NULL DEFAULT 'KZT',
    starts_at        TIMESTAMPTZ,
    ends_at          TIMESTAMPTZ,
    max_redemptions  INTEGER CHECK (max_redemptions IS NULL OR max_redemptions > 0),
    redemption_count INTEGER NOT NULL DEFAULT 0 CHECK (redemption_count >= 0),
    status           campaign_status NOT NULL DEFAULT 'draft',
    created_by       UUID REFERENCES users(id) ON DELETE SET NULL,
    created_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT campaigns_percent_range CHECK (
        discount_type <> 'percent' OR discount_value <= 100),
    CONSTRAINT campaigns_window CHECK (
        starts_at IS NULL OR ends_at IS NULL OR ends_at > starts_at),
    CONSTRAINT campaigns_within_limit CHECK (
        max_redemptions IS NULL OR redemption_count <= max_redemptions)
);

CREATE TABLE promo_codes (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    campaign_id UUID NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
    code        CITEXT NOT NULL UNIQUE,
    is_active   BOOLEAN NOT NULL DEFAULT true,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE campaign_qr_codes (
    id          UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    campaign_id UUID NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
    token       TEXT NOT NULL UNIQUE,
    target_url  TEXT NOT NULL,
    image_url   TEXT,
    label       TEXT,
    scan_count  BIGINT NOT NULL DEFAULT 0,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE campaign_ticket_types (
    campaign_id    UUID NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
    ticket_type_id UUID NOT NULL REFERENCES ticket_types(id) ON DELETE CASCADE,
    PRIMARY KEY (campaign_id, ticket_type_id)
);

-- 6. Orders, attendees, payments

CREATE TABLE orders (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    order_number    TEXT NOT NULL UNIQUE,
    event_id        UUID NOT NULL REFERENCES events(id) ON DELETE RESTRICT,
    buyer_user_id   UUID REFERENCES users(id) ON DELETE SET NULL,
    buyer_email     CITEXT NOT NULL,
    buyer_name      TEXT NOT NULL,
    buyer_phone     TEXT,
    status          order_status NOT NULL DEFAULT 'pending',
    currency        CHAR(3) NOT NULL DEFAULT 'KZT',
    subtotal_amount BIGINT NOT NULL DEFAULT 0 CHECK (subtotal_amount >= 0),
    discount_amount BIGINT NOT NULL DEFAULT 0 CHECK (discount_amount >= 0),
    fee_amount      BIGINT NOT NULL DEFAULT 0 CHECK (fee_amount >= 0),
    total_amount    BIGINT NOT NULL DEFAULT 0 CHECK (total_amount >= 0),
    promo_code_id   UUID REFERENCES promo_codes(id) ON DELETE SET NULL,
    campaign_id     UUID REFERENCES campaigns(id) ON DELETE SET NULL,
    is_simulated    BOOLEAN NOT NULL DEFAULT true,
    placed_at       TIMESTAMPTZ,
    expires_at      TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT orders_totals_consistent CHECK (
        total_amount = subtotal_amount - discount_amount + fee_amount),
    CONSTRAINT orders_discount_within_subtotal CHECK (discount_amount <= subtotal_amount)
);

CREATE INDEX ix_orders_event_placed ON orders (event_id, placed_at DESC);
CREATE INDEX ix_orders_buyer_user   ON orders (buyer_user_id);
CREATE INDEX ix_orders_buyer_email  ON orders (buyer_email);
CREATE INDEX ix_orders_expiring     ON orders (expires_at)
    WHERE status IN ('pending', 'awaiting_payment');

ALTER TABLE seat_holds
    ADD CONSTRAINT fk_seat_holds_order
    FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE SET NULL;

CREATE TABLE order_items (
    id                UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    order_id          UUID NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
    ticket_type_id    UUID NOT NULL REFERENCES ticket_types(id) ON DELETE RESTRICT,
    seat_id           UUID REFERENCES seats(id) ON DELETE RESTRICT,
    quantity          INTEGER NOT NULL DEFAULT 1 CHECK (quantity > 0),
    unit_price_amount BIGINT NOT NULL CHECK (unit_price_amount >= 0),
    discount_amount   BIGINT NOT NULL DEFAULT 0 CHECK (discount_amount >= 0),
    line_total        BIGINT NOT NULL CHECK (line_total >= 0),
    CONSTRAINT order_items_seat_is_single CHECK (seat_id IS NULL OR quantity = 1),
    CONSTRAINT order_items_line_total CHECK (
        line_total = unit_price_amount * quantity - discount_amount)
);
CREATE INDEX ix_order_items_order       ON order_items (order_id);
CREATE INDEX ix_order_items_ticket_type ON order_items (ticket_type_id);

CREATE TABLE attendees (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    order_item_id UUID NOT NULL REFERENCES order_items(id) ON DELETE CASCADE,
    user_id       UUID REFERENCES users(id) ON DELETE SET NULL,
    full_name     TEXT NOT NULL,
    email         CITEXT,
    phone         TEXT,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE payments (
    id                   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    order_id             UUID REFERENCES orders(id) ON DELETE RESTRICT,
    purpose              payment_purpose NOT NULL,
    provider             TEXT NOT NULL,
    provider_payment_ref TEXT,
    status               payment_status NOT NULL DEFAULT 'initiated',
    amount               BIGINT NOT NULL CHECK (amount >= 0),
    currency             CHAR(3) NOT NULL DEFAULT 'KZT',
    is_simulated         BOOLEAN NOT NULL DEFAULT true,
    failure_reason       TEXT,
    provider_payload     JSONB,
    processed_at         TIMESTAMPTZ,
    created_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (provider, provider_payment_ref),
    CONSTRAINT payments_ticket_needs_order CHECK (
        purpose <> 'ticket_purchase' OR order_id IS NOT NULL)
);
CREATE INDEX ix_payments_order ON payments (order_id);

CREATE TABLE refunds (
    id                   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    payment_id           UUID NOT NULL REFERENCES payments(id) ON DELETE RESTRICT,
    order_id             UUID NOT NULL REFERENCES orders(id) ON DELETE RESTRICT,
    initiated_by_user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    amount               BIGINT NOT NULL CHECK (amount > 0),
    currency             CHAR(3) NOT NULL DEFAULT 'KZT',
    reason               TEXT,
    status               refund_status NOT NULL DEFAULT 'requested',
    provider_refund_ref  TEXT,
    is_simulated         BOOLEAN NOT NULL DEFAULT true,
    processed_at         TIMESTAMPTZ,
    created_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at           TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX ix_refunds_order ON refunds (order_id);

CREATE TABLE paid_sales_activations (
    id                   UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    event_id             UUID NOT NULL UNIQUE REFERENCES events(id) ON DELETE CASCADE,
    organizer_profile_id UUID NOT NULL REFERENCES organizer_profiles(id) ON DELETE RESTRICT,
    payout_account_id    UUID REFERENCES payout_accounts(id) ON DELETE RESTRICT,
    fee_payment_id       UUID REFERENCES payments(id) ON DELETE SET NULL,
    fee_amount           BIGINT NOT NULL CHECK (fee_amount >= 0),
    currency             CHAR(3) NOT NULL DEFAULT 'KZT',
    identity_verified_at TIMESTAMPTZ,
    terms_accepted_at    TIMESTAMPTZ,
    status               activation_status NOT NULL DEFAULT 'pending',
    activated_at         TIMESTAMPTZ,
    suspended_at         TIMESTAMPTZ,
    suspended_by         UUID REFERENCES users(id) ON DELETE SET NULL,
    suspension_reason    TEXT,
    created_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at           TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT activation_checklist_complete CHECK (
        status <> 'active' OR (
            identity_verified_at IS NOT NULL
            AND terms_accepted_at IS NOT NULL
            AND payout_account_id IS NOT NULL
            AND fee_payment_id  IS NOT NULL))
);

CREATE TABLE promo_redemptions (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    promo_code_id   UUID NOT NULL REFERENCES promo_codes(id) ON DELETE RESTRICT,
    campaign_id     UUID NOT NULL REFERENCES campaigns(id) ON DELETE RESTRICT,
    order_id        UUID NOT NULL UNIQUE REFERENCES orders(id) ON DELETE CASCADE,
    user_id         UUID REFERENCES users(id) ON DELETE SET NULL,
    discount_amount BIGINT NOT NULL CHECK (discount_amount > 0),
    currency        CHAR(3) NOT NULL DEFAULT 'KZT',
    redeemed_at     TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX ix_promo_redemptions_campaign ON promo_redemptions (campaign_id, redeemed_at DESC);

-- 7. Tickets and check-in

CREATE TABLE tickets (
    id                 UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ticket_code        TEXT NOT NULL UNIQUE,
    qr_token           TEXT NOT NULL UNIQUE,
    order_item_id      UUID NOT NULL REFERENCES order_items(id) ON DELETE RESTRICT,
    event_id           UUID NOT NULL REFERENCES events(id) ON DELETE RESTRICT,
    ticket_type_id     UUID NOT NULL REFERENCES ticket_types(id) ON DELETE RESTRICT,
    attendee_id        UUID NOT NULL REFERENCES attendees(id) ON DELETE RESTRICT,
    seat_id            UUID REFERENCES seats(id) ON DELETE RESTRICT,
    seat_section_label TEXT,
    seat_row_label     TEXT,
    seat_number_label  TEXT,
    status             ticket_status NOT NULL DEFAULT 'valid',
    issued_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    checked_in_at      TIMESTAMPTZ,
    invalidated_at     TIMESTAMPTZ,
    pdf_url            TEXT,
    created_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at         TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT tickets_seat_labels_present CHECK (
        seat_id IS NULL OR (
            seat_section_label IS NOT NULL
            AND seat_row_label IS NOT NULL
            AND seat_number_label IS NOT NULL))
);

CREATE UNIQUE INDEX uq_tickets_assigned_seat
    ON tickets (event_id, seat_id)
    WHERE seat_id IS NOT NULL AND status IN ('valid', 'checked_in');
CREATE INDEX ix_tickets_event_status ON tickets (event_id, status);
CREATE INDEX ix_tickets_order_item   ON tickets (order_item_id);

CREATE TABLE check_in_records (
    id                 UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    ticket_id          UUID REFERENCES tickets(id) ON DELETE SET NULL,
    event_id           UUID NOT NULL REFERENCES events(id) ON DELETE CASCADE,
    scanned_by_user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    device_id          TEXT,
    action             check_in_action NOT NULL,
    result             check_in_result NOT NULL,
    source             check_in_source NOT NULL DEFAULT 'qr_scan',
    scanned_token      TEXT,
    reverses_record_id UUID REFERENCES check_in_records(id) ON DELETE SET NULL,
    notes              TEXT,
    scanned_at         TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX ix_check_in_event_time ON check_in_records (event_id, scanned_at DESC);
CREATE INDEX ix_check_in_ticket     ON check_in_records (ticket_id);

-- 8. Support

CREATE TABLE support_cases (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    case_number         TEXT NOT NULL UNIQUE,
    case_type           support_case_type NOT NULL,
    category            support_category NOT NULL,
    subject             TEXT NOT NULL,
    opened_by_user_id   UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    event_id            UUID REFERENCES events(id) ON DELETE SET NULL,
    order_id            UUID REFERENCES orders(id) ON DELETE SET NULL,
    ticket_id           UUID REFERENCES tickets(id) ON DELETE SET NULL,
    status              support_status NOT NULL DEFAULT 'open',
    assigned_to_user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    last_message_at     TIMESTAMPTZ,
    resolved_at         TIMESTAMPTZ,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    CONSTRAINT support_attendee_case_has_context CHECK (
        case_type <> 'attendee'
        OR event_id IS NOT NULL OR order_id IS NOT NULL OR ticket_id IS NOT NULL)
);
CREATE INDEX ix_support_cases_status   ON support_cases (status, updated_at DESC);
CREATE INDEX ix_support_cases_event    ON support_cases (event_id);
CREATE INDEX ix_support_cases_assignee ON support_cases (assigned_to_user_id);

CREATE TABLE support_messages (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    case_id         UUID NOT NULL REFERENCES support_cases(id) ON DELETE CASCADE,
    sender_user_id  UUID NOT NULL REFERENCES users(id) ON DELETE RESTRICT,
    sender_role     support_sender_role NOT NULL,
    body            TEXT NOT NULL,
    is_internal_note BOOLEAN NOT NULL DEFAULT false,
    read_at         TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX ix_support_messages_case ON support_messages (case_id, created_at);

CREATE TABLE support_attachments (
    id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    message_id UUID NOT NULL REFERENCES support_messages(id) ON DELETE CASCADE,
    file_url   TEXT NOT NULL,
    filename   TEXT NOT NULL,
    mime_type  TEXT NOT NULL,
    size_bytes BIGINT NOT NULL CHECK (size_bytes > 0),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- 9. Notifications and audit

CREATE TABLE notifications (
    id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id             UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    type                notification_type NOT NULL,
    channel             notification_channel NOT NULL,
    related_entity_type TEXT,
    related_entity_id   TEXT,
    template_key        TEXT NOT NULL,
    payload             JSONB NOT NULL DEFAULT '{}'::jsonb,
    status              notification_status NOT NULL DEFAULT 'queued',
    error_message       TEXT,
    sent_at             TIMESTAMPTZ,
    read_at             TIMESTAMPTZ,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX ix_notifications_user   ON notifications (user_id, created_at DESC);
CREATE INDEX ix_notifications_queued ON notifications (created_at) WHERE status = 'queued';

CREATE TABLE audit_logs (
    id            BIGSERIAL PRIMARY KEY,
    occurred_at   TIMESTAMPTZ NOT NULL DEFAULT now(),
    actor_user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    actor_role    TEXT,
    action_type   TEXT NOT NULL,
    entity_type   TEXT NOT NULL,
    entity_id     TEXT NOT NULL,
    event_id      UUID REFERENCES events(id) ON DELETE SET NULL,
    summary       TEXT NOT NULL,
    metadata      JSONB NOT NULL DEFAULT '{}'::jsonb,
    ip_address    INET
);
CREATE INDEX ix_audit_logs_event  ON audit_logs (event_id, occurred_at DESC);
CREATE INDEX ix_audit_logs_entity ON audit_logs (entity_type, entity_id);
CREATE INDEX ix_audit_logs_action ON audit_logs (action_type, occurred_at DESC);

CREATE TRIGGER trg_audit_logs_immutable
    BEFORE UPDATE OR DELETE ON audit_logs
    FOR EACH ROW EXECUTE FUNCTION prevent_mutation();

-- 10. updated_at triggers

DO $$
DECLARE
    tbl TEXT;
BEGIN
    FOREACH tbl IN ARRAY ARRAY[
        'users', 'organizer_profiles', 'payout_accounts', 'venues', 'events',
        'ticket_types', 'campaigns', 'orders', 'payments', 'refunds',
        'paid_sales_activations', 'tickets', 'support_cases'
    ] LOOP
        EXECUTE format(
            'CREATE TRIGGER %I BEFORE UPDATE ON %I FOR EACH ROW EXECUTE FUNCTION set_updated_at()',
            'trg_' || tbl || '_updated_at', tbl);
    END LOOP;
END $$;

COMMIT;
