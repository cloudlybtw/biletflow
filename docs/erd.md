# BiletFlow — Entity Relationship Diagram

Hand-authored from `backend/migrations/0001_init_schema.up.sql` and
`0002_platform_support.up.sql`. Update this file whenever a migration adds,
removes or changes a table or relationship. Diagrams are grouped by the same
numbered sections used in the migration files; only relationships *within*
each section are drawn — FKs that cross section boundaries are listed once in
the "Cross-section references" table at the end instead of one unreadable
35-table diagram.

## 1. Identity and access

```mermaid
erDiagram
    USERS ||--o| ORGANIZER_PROFILES : "has (optional)"
    ORGANIZER_PROFILES ||--o{ PAYOUT_ACCOUNTS : has

    USERS {
        uuid id PK
        citext email UK
        platform_role platform_role
        user_status status
    }
    ORGANIZER_PROFILES {
        uuid id PK
        uuid user_id FK "UK"
        verification_status verification_status
    }
    PAYOUT_ACCOUNTS {
        uuid id PK
        uuid organizer_profile_id FK
        payout_account_status status
        bool is_default "one default per organizer (partial UK)"
    }
```

## 2. Venues and seating

```mermaid
erDiagram
    VENUES ||--o{ PRICE_CATEGORIES : defines
    VENUES ||--o{ VENUE_SECTIONS : has
    VENUE_SECTIONS ||--o{ VENUE_ROWS : has
    VENUE_ROWS ||--o{ SEATS : has
    PRICE_CATEGORIES ||--o{ SEATS : "prices (nullable)"

    VENUES {
        uuid id PK
        text name
        bool is_predefined
    }
    PRICE_CATEGORIES {
        uuid id PK
        uuid venue_id FK
        text code "UK per venue"
    }
    VENUE_SECTIONS {
        uuid id PK
        uuid venue_id FK
        text name "UK per venue"
    }
    VENUE_ROWS {
        uuid id PK
        uuid section_id FK
        text label "UK per section"
    }
    SEATS {
        uuid id PK
        uuid row_id FK
        uuid price_category_id FK
        text seat_number "UK per row"
    }
```

## 3. Events

```mermaid
erDiagram
    EVENT_CATEGORIES ||--o{ EVENTS : categorizes
    EVENTS ||--o{ EVENT_IMAGES : has
    EVENTS ||--o{ STAFF_ASSIGNMENTS : has

    EVENT_CATEGORIES {
        uuid id PK
        text slug UK
    }
    EVENTS {
        uuid id PK
        uuid organizer_profile_id FK
        uuid venue_id FK "nullable"
        uuid category_id FK "nullable"
        text slug UK
        event_visibility visibility
        event_status status
        seating_mode seating_mode
        paid_sales_status paid_sales_status
    }
    EVENT_IMAGES {
        uuid id PK
        uuid event_id FK
        bool is_cover "one cover per event (partial UK)"
    }
    STAFF_ASSIGNMENTS {
        uuid id PK
        uuid event_id FK
        uuid user_id FK
        staff_role role
        timestamptz revoked_at "active when NULL (partial UK on event+user+role)"
    }
```

## 4. Ticket inventory and seat holds

```mermaid
erDiagram
    TICKET_TYPES ||--o{ EVENT_PRICE_CATEGORY_TICKET_TYPES : maps
    TICKET_TYPES ||--o{ SEAT_HOLDS : holds

    TICKET_TYPES {
        uuid id PK
        uuid event_id FK
        text name "UK per event"
        bigint price_amount
        int quantity_total
        int quantity_reserved
        int quantity_sold
    }
    EVENT_PRICE_CATEGORY_TICKET_TYPES {
        uuid event_id PK_FK
        uuid price_category_id PK_FK
        uuid ticket_type_id FK
    }
    SEAT_HOLDS {
        uuid id PK
        uuid event_id FK
        uuid seat_id FK
        uuid ticket_type_id FK
        uuid order_id FK "nullable"
        seat_hold_status status "one active hold per seat (partial UK)"
    }
```

## 5. Promotions

```mermaid
erDiagram
    CAMPAIGNS ||--o{ PROMO_CODES : has
    CAMPAIGNS ||--o{ CAMPAIGN_QR_CODES : has
    CAMPAIGNS ||--o{ CAMPAIGN_TICKET_TYPES : "applies to"

    CAMPAIGNS {
        uuid id PK
        uuid event_id FK
        discount_type discount_type
        bigint discount_value
        campaign_status status
        int redemption_count
        int max_redemptions "nullable"
    }
    PROMO_CODES {
        uuid id PK
        uuid campaign_id FK
        citext code UK
        bool is_active
    }
    CAMPAIGN_QR_CODES {
        uuid id PK
        uuid campaign_id FK
        text token UK
    }
    CAMPAIGN_TICKET_TYPES {
        uuid campaign_id PK_FK
        uuid ticket_type_id PK_FK
    }
```

## 6. Orders, attendees, payments

```mermaid
erDiagram
    ORDERS ||--o{ ORDER_ITEMS : contains
    ORDER_ITEMS ||--o{ ATTENDEES : has
    ORDERS ||--o{ PAYMENTS : has
    PAYMENTS ||--o{ REFUNDS : has
    ORDERS ||--o{ REFUNDS : has
    ORDERS ||--o| PROMO_REDEMPTIONS : has

    ORDERS {
        uuid id PK
        text order_number UK
        uuid event_id FK
        uuid buyer_user_id FK "nullable"
        order_status status
        bigint subtotal_amount
        bigint discount_amount
        bigint fee_amount
        bigint total_amount
        bool is_simulated
    }
    ORDER_ITEMS {
        uuid id PK
        uuid order_id FK
        uuid ticket_type_id FK
        uuid seat_id FK "nullable"
        int quantity
        bigint line_total
    }
    ATTENDEES {
        uuid id PK
        uuid order_item_id FK
        uuid user_id FK "nullable"
        text full_name
    }
    PAYMENTS {
        uuid id PK
        uuid order_id FK "nullable"
        payment_purpose purpose
        payment_status status
        bigint amount
        bool is_simulated
    }
    REFUNDS {
        uuid id PK
        uuid payment_id FK
        uuid order_id FK
        refund_status status
        bigint amount
        bool is_simulated
    }
    PAID_SALES_ACTIVATIONS {
        uuid id PK
        uuid event_id FK "UK"
        uuid organizer_profile_id FK
        uuid payout_account_id FK "nullable"
        uuid fee_payment_id FK "nullable"
        activation_status status
    }
    PROMO_REDEMPTIONS {
        uuid id PK
        uuid promo_code_id FK
        uuid campaign_id FK
        uuid order_id FK "UK"
        bigint discount_amount
    }
```

## 7. Tickets and check-in

```mermaid
erDiagram
    TICKETS ||--o{ CHECK_IN_RECORDS : "scanned via"
    CHECK_IN_RECORDS ||--o| CHECK_IN_RECORDS : reverses

    TICKETS {
        uuid id PK
        text ticket_code UK
        text qr_token UK
        uuid order_item_id FK
        uuid event_id FK
        uuid ticket_type_id FK
        uuid attendee_id FK
        uuid seat_id FK "nullable, one ticket per seat while valid (partial UK)"
        ticket_status status
    }
    CHECK_IN_RECORDS {
        uuid id PK
        uuid ticket_id FK "nullable"
        uuid event_id FK
        uuid scanned_by_user_id FK "nullable"
        uuid reverses_record_id FK "nullable, self-reference"
        check_in_action action
        check_in_result result
        check_in_source source
    }
```

## 8. Support

```mermaid
erDiagram
    SUPPORT_CASES ||--o{ SUPPORT_MESSAGES : has
    SUPPORT_MESSAGES ||--o{ SUPPORT_ATTACHMENTS : has

    SUPPORT_CASES {
        uuid id PK
        text case_number UK
        support_case_type case_type
        support_category category
        uuid opened_by_user_id FK
        uuid event_id FK "nullable"
        uuid order_id FK "nullable"
        uuid ticket_id FK "nullable"
        support_status status
        uuid assigned_to_user_id FK "nullable"
    }
    SUPPORT_MESSAGES {
        uuid id PK
        uuid case_id FK
        uuid sender_user_id FK
        support_sender_role sender_role
        bool is_internal_note
    }
    SUPPORT_ATTACHMENTS {
        uuid id PK
        uuid message_id FK
        text file_url
    }
```

## 9. Notifications and audit

```mermaid
erDiagram
    NOTIFICATIONS {
        uuid id PK
        uuid user_id FK
        notification_type type
        notification_channel channel
        notification_status status
    }
    AUDIT_LOGS {
        bigint id PK
        uuid actor_user_id FK "nullable"
        text action_type
        text entity_type
        text entity_id
        uuid event_id FK "nullable"
        jsonb metadata
    }
```

`audit_logs` is append-only (a `BEFORE UPDATE OR DELETE` trigger blocks
mutation); no other section-9 relationships exist beyond the FKs listed
below.

## 10. Platform support (0002)

```mermaid
erDiagram
    USER_TOKENS {
        uuid id PK
        uuid user_id FK
        user_token_purpose purpose
        text token_hash UK
        timestamptz expires_at
        timestamptz used_at "nullable"
    }
    PLATFORM_SETTINGS {
        text key PK
        jsonb value
        uuid updated_by FK "nullable"
    }
```

Seeded `platform_settings` rows: `activation_fee_kzt`, `processing_fee_percent`,
`order_hold_minutes`, `seat_hold_minutes`.

## Cross-section references

FKs that cross the section boundaries above:

| Column | References |
|---|---|
| `organizer_profiles.user_id` | `users.id` |
| `payout_accounts.organizer_profile_id` | `organizer_profiles.id` |
| `venues.created_by` | `users.id` |
| `events.organizer_profile_id` | `organizer_profiles.id` |
| `events.venue_id` | `venues.id` |
| `events.category_id` | `event_categories.id` |
| `staff_assignments.user_id` / `assigned_by` | `users.id` |
| `ticket_types.event_id` | `events.id` |
| `event_price_category_ticket_types.price_category_id` | `price_categories.id` |
| `event_price_category_ticket_types.event_id` | `events.id` |
| `seat_holds.event_id` | `events.id` |
| `seat_holds.seat_id` | `seats.id` |
| `seat_holds.held_by_user_id` | `users.id` |
| `seat_holds.order_id` | `orders.id` (added after `orders` exists) |
| `campaigns.event_id` | `events.id` |
| `campaigns.created_by` | `users.id` |
| `campaign_ticket_types.ticket_type_id` | `ticket_types.id` |
| `orders.event_id` | `events.id` |
| `orders.buyer_user_id` | `users.id` |
| `orders.promo_code_id` | `promo_codes.id` |
| `orders.campaign_id` | `campaigns.id` |
| `order_items.ticket_type_id` | `ticket_types.id` |
| `order_items.seat_id` | `seats.id` |
| `attendees.user_id` | `users.id` |
| `paid_sales_activations.event_id` | `events.id` |
| `paid_sales_activations.organizer_profile_id` | `organizer_profiles.id` |
| `paid_sales_activations.payout_account_id` | `payout_accounts.id` |
| `paid_sales_activations.fee_payment_id` | `payments.id` |
| `tickets.order_item_id` | `order_items.id` |
| `tickets.event_id` | `events.id` |
| `tickets.ticket_type_id` | `ticket_types.id` |
| `tickets.attendee_id` | `attendees.id` |
| `tickets.seat_id` | `seats.id` |
| `check_in_records.event_id` | `events.id` |
| `check_in_records.ticket_id` | `tickets.id` |
| `check_in_records.scanned_by_user_id` | `users.id` |
| `support_cases.opened_by_user_id` / `assigned_to_user_id` | `users.id` |
| `support_cases.event_id` / `order_id` / `ticket_id` | `events.id` / `orders.id` / `tickets.id` |
| `support_messages.sender_user_id` | `users.id` |
| `notifications.user_id` | `users.id` |
| `audit_logs.actor_user_id` | `users.id` |
| `audit_logs.event_id` | `events.id` |
| `user_tokens.user_id` | `users.id` |
| `platform_settings.updated_by` | `users.id` |
