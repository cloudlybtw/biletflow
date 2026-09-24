BEGIN;

-- 11. Platform support

CREATE TYPE user_token_purpose AS ENUM ('email_verify', 'password_reset', 'refresh');

CREATE TABLE user_tokens (
    id         UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id    UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    purpose    user_token_purpose NOT NULL,
    token_hash TEXT NOT NULL UNIQUE,
    expires_at TIMESTAMPTZ NOT NULL,
    used_at    TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX ix_user_tokens_user_id ON user_tokens (user_id);
CREATE INDEX ix_user_tokens_active  ON user_tokens (user_id, purpose) WHERE used_at IS NULL;

CREATE TABLE platform_settings (
    key        TEXT PRIMARY KEY,
    value      JSONB NOT NULL,
    updated_by UUID REFERENCES users(id) ON DELETE SET NULL,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TRIGGER trg_platform_settings_updated_at
    BEFORE UPDATE ON platform_settings
    FOR EACH ROW EXECUTE FUNCTION set_updated_at();

INSERT INTO platform_settings (key, value) VALUES
    ('activation_fee_kzt',     '5000'),
    ('processing_fee_percent', '0'),
    ('order_hold_minutes',     '15'),
    ('seat_hold_minutes',      '10');

COMMIT;
