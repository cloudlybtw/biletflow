BEGIN;
-- Preserve the exact promo associated with each QR if a campaign has several codes.
ALTER TABLE campaign_qr_codes ADD COLUMN promo_code_id UUID REFERENCES promo_codes(id) ON DELETE CASCADE;
UPDATE campaign_qr_codes q SET promo_code_id = (
    SELECT p.id FROM promo_codes p WHERE p.campaign_id = q.campaign_id ORDER BY p.created_at, p.id LIMIT 1
);
-- Historical campaigns without promo codes cannot produce redeemable links.
DELETE FROM campaign_qr_codes WHERE promo_code_id IS NULL;
ALTER TABLE campaign_qr_codes ALTER COLUMN promo_code_id SET NOT NULL;
COMMIT;
