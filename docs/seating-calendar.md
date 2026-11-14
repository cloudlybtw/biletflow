# Assigned seats and calendar updates

Apply migration `0009_seat_configuration` before running this version. Existing
assigned events require explicit category mappings in the organizer's ticket tab;
unmapped seats are unavailable. General-admission events are unaffected.

In an assigned event, select the predefined venue and create ticket types. Under
**Tickets → Seat pricing and availability**, assign each venue price category to
one visible event ticket type (or clear the mapping). Use the seat/reason/block
form to block or reopen individual seats. Configuration is event-scoped, audited,
and restricted to the owner/co-organizers. Held/sold seats cannot be blocked and
categories with active holds or valid tickets cannot be remapped. Refund/release
first. Changing a ticket price uses the existing authoritative ticket-type price;
orders keep their price snapshots.

The buyer sees a spatial grid using the venue's row/seat coordinates, category,
price, status and accessible label. Select a ticket type, select compatible seats,
review the selected total, then hold them before checkout. Other categories and
unavailable seats cannot be selected. Holds reserve seats temporarily and refresh
on the existing polling interval. Switching ticket type clears unsaved selection;
existing holds can be released. The backend validates seat/category/type at hold
creation and again at checkout, including forged or stale holds.

Statuses are exposed in text as well as visual styling: available, selected,
held (including own hold), sold, unavailable and accessible. Native checkboxes
support keyboard operation. Large layouts scroll within the seat region. This
is the predefined layout feature, not a venue designer.

Calendar links are available on event pages and completed order confirmations.
Relevant event edits increment `ics_sequence`; no-op edits do not. Cancellation
increments it again and exports `STATUS:CANCELLED`. UID remains stable. ICS includes
UTC instants, configured timezone metadata, venue/address, description and event
URL. Google links include timezone, and both common-calendar links include the
event URL. These downloadable exports do not automatically push updates to a
calendar account; import the updated file where the calendar client supports it.
