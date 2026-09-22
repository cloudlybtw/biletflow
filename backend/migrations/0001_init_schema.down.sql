BEGIN;

DROP TABLE IF EXISTS audit_logs                        CASCADE;
DROP TABLE IF EXISTS notifications                     CASCADE;

DROP TABLE IF EXISTS support_attachments               CASCADE;
DROP TABLE IF EXISTS support_messages                  CASCADE;
DROP TABLE IF EXISTS support_cases                     CASCADE;

DROP TABLE IF EXISTS check_in_records                  CASCADE;
DROP TABLE IF EXISTS tickets                           CASCADE;

DROP TABLE IF EXISTS paid_sales_activations            CASCADE;
DROP TABLE IF EXISTS refunds                           CASCADE;
DROP TABLE IF EXISTS payments                          CASCADE;
DROP TABLE IF EXISTS attendees                         CASCADE;
DROP TABLE IF EXISTS order_items                       CASCADE;
DROP TABLE IF EXISTS orders                            CASCADE;

DROP TABLE IF EXISTS campaign_ticket_types             CASCADE;
DROP TABLE IF EXISTS campaign_qr_codes                 CASCADE;
DROP TABLE IF EXISTS promo_redemptions                 CASCADE;
DROP TABLE IF EXISTS promo_codes                       CASCADE;
DROP TABLE IF EXISTS campaigns                         CASCADE;

DROP TABLE IF EXISTS seat_holds                        CASCADE;
DROP TABLE IF EXISTS event_price_category_ticket_types CASCADE;
DROP TABLE IF EXISTS ticket_types                      CASCADE;

DROP TABLE IF EXISTS staff_assignments                 CASCADE;
DROP TABLE IF EXISTS event_images                      CASCADE;
DROP TABLE IF EXISTS events                            CASCADE;
DROP TABLE IF EXISTS event_categories                  CASCADE;

DROP TABLE IF EXISTS seats                             CASCADE;
DROP TABLE IF EXISTS venue_rows                        CASCADE;
DROP TABLE IF EXISTS venue_sections                    CASCADE;
DROP TABLE IF EXISTS price_categories                  CASCADE;
DROP TABLE IF EXISTS venues                            CASCADE;

DROP TABLE IF EXISTS payout_accounts                   CASCADE;
DROP TABLE IF EXISTS organizer_profiles                CASCADE;
DROP TABLE IF EXISTS users                             CASCADE;

DROP TYPE IF EXISTS notification_type;
DROP TYPE IF EXISTS notification_status;
DROP TYPE IF EXISTS notification_channel;
DROP TYPE IF EXISTS support_sender_role;
DROP TYPE IF EXISTS support_status;
DROP TYPE IF EXISTS support_category;
DROP TYPE IF EXISTS support_case_type;
DROP TYPE IF EXISTS campaign_status;
DROP TYPE IF EXISTS discount_type;
DROP TYPE IF EXISTS check_in_source;
DROP TYPE IF EXISTS check_in_result;
DROP TYPE IF EXISTS check_in_action;
DROP TYPE IF EXISTS ticket_status;
DROP TYPE IF EXISTS refund_status;
DROP TYPE IF EXISTS payment_status;
DROP TYPE IF EXISTS payment_purpose;
DROP TYPE IF EXISTS order_status;
DROP TYPE IF EXISTS seat_hold_status;
DROP TYPE IF EXISTS activation_status;
DROP TYPE IF EXISTS paid_sales_status;
DROP TYPE IF EXISTS seating_mode;
DROP TYPE IF EXISTS event_status;
DROP TYPE IF EXISTS event_visibility;
DROP TYPE IF EXISTS staff_role;
DROP TYPE IF EXISTS payout_account_status;
DROP TYPE IF EXISTS verification_status;
DROP TYPE IF EXISTS user_status;
DROP TYPE IF EXISTS platform_role;

DROP FUNCTION IF EXISTS prevent_mutation();
DROP FUNCTION IF EXISTS set_updated_at();

COMMIT;
