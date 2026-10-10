BEGIN;
ALTER TABLE campaign_qr_codes DROP COLUMN promo_code_id;
COMMIT;
