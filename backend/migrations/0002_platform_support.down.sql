BEGIN;

DROP TRIGGER IF EXISTS trg_platform_settings_updated_at ON platform_settings;
DROP TABLE IF EXISTS platform_settings CASCADE;
DROP TABLE IF EXISTS user_tokens CASCADE;
DROP TYPE IF EXISTS user_token_purpose;

COMMIT;
