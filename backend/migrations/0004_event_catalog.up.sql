BEGIN;

-- Soft deletion retains immutable audit rows and never deletes sold inventory.
ALTER TABLE events ADD COLUMN deleted_at TIMESTAMPTZ;

INSERT INTO event_categories (id, slug, name_kk, name_ru, name_en, display_order) VALUES
('10000000-0000-0000-0000-000000000001', 'music', 'Музыка', 'Музыка', 'Music', 1),
('10000000-0000-0000-0000-000000000002', 'theatre', 'Театр', 'Театр', 'Theatre', 2),
('10000000-0000-0000-0000-000000000003', 'sports', 'Спорт', 'Спорт', 'Sports', 3),
('10000000-0000-0000-0000-000000000004', 'education', 'Білім', 'Образование', 'Education', 4);

INSERT INTO venues (id, name, address_line, city, is_predefined) VALUES
('20000000-0000-0000-0000-000000000001', 'BiletFlow Demo Hall', '1 Demo Street', 'Almaty', true);
INSERT INTO price_categories (id, venue_id, code, name, display_color) VALUES
('30000000-0000-0000-0000-000000000001', '20000000-0000-0000-0000-000000000001', 'STANDARD', 'Standard', '#2563eb'),
('30000000-0000-0000-0000-000000000002', '20000000-0000-0000-0000-000000000001', 'PREMIUM', 'Premium', '#9333ea');
INSERT INTO venue_sections (id, venue_id, name, display_order) VALUES
('40000000-0000-0000-0000-000000000001', '20000000-0000-0000-0000-000000000001', 'Main', 1);
INSERT INTO venue_rows (id, section_id, label, display_order) VALUES
('50000000-0000-0000-0000-000000000001', '40000000-0000-0000-0000-000000000001', 'A', 1),
('50000000-0000-0000-0000-000000000002', '40000000-0000-0000-0000-000000000001', 'B', 2);
INSERT INTO seats (row_id, price_category_id, seat_number, is_accessible, position_x, position_y)
SELECT r.id, CASE WHEN r.label = 'A' THEN '30000000-0000-0000-0000-000000000002'::uuid
ELSE '30000000-0000-0000-0000-000000000001'::uuid END,
n::text, n = 1, n * 30, r.display_order * 40
FROM venue_rows r CROSS JOIN generate_series(1, 10) n
WHERE r.section_id = '40000000-0000-0000-0000-000000000001';
COMMIT;
