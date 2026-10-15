"""Exact snapshot reports. Queries never expire orders or acquire row locks.

Refunds are aggregated before joining items. Cumulative floor allocation assigns
whole-tenge fees/refunds in item UUID order, preserving every order total.
"""

import uuid

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.errors import NOT_FOUND, AppError
from app.core.reporting import ReportFilters
from app.modules.ticketing.models import TicketType

# SQL fragments below are developer-owned constants; all user input is bound.
BASE = """
WITH cohort AS (
    SELECT o.* FROM orders o WHERE o.event_id = :event_id
      AND (CAST(:date_from AS timestamptz) IS NULL OR o.placed_at >= :date_from)
      AND (CAST(:date_to AS timestamptz) IS NULL OR o.placed_at < :date_to)
), refund_totals AS (
    SELECT r.order_id, sum(r.amount)::numeric AS amount
    FROM refunds r JOIN cohort o ON o.id = r.order_id
    WHERE r.status = 'completed' GROUP BY r.order_id
), issued_orders AS (
    SELECT o.*, coalesce(r.amount, 0) AS refunded,
      CASE WHEN o.total_amount > 0
        THEN floor(coalesce(r.amount, 0) * o.fee_amount / o.total_amount)
        ELSE 0 END AS refunded_fee
    FROM cohort o LEFT JOIN refund_totals r ON r.order_id = o.id
    WHERE o.status IN ('completed', 'refunded', 'partially_refunded', 'cancelled')
      AND EXISTS (SELECT 1 FROM order_items i JOIN tickets t ON t.order_item_id = i.id
                  WHERE i.order_id = o.id)
), weighted AS (
    SELECT i.*, o.status, o.placed_at, o.campaign_id, o.promo_code_id,
      o.fee_amount AS order_fee, o.subtotal_amount - o.discount_amount AS weight_total,
      o.refunded - o.refunded_fee AS refunded_ticket, o.refunded_fee,
      sum(i.line_total::numeric) OVER (PARTITION BY i.order_id ORDER BY i.id) AS cumulative
    FROM issued_orders o JOIN order_items i ON i.order_id = o.id
), lines AS (
    SELECT w.*,
      CASE WHEN weight_total > 0 THEN
        floor(order_fee * cumulative / weight_total) -
        floor(order_fee * (cumulative - line_total) / weight_total) ELSE 0 END AS fee,
      CASE WHEN weight_total > 0 THEN
        floor(refunded_ticket * cumulative / weight_total) -
        floor(refunded_ticket * (cumulative - line_total) / weight_total) ELSE 0 END AS ticket_refund,
      CASE WHEN weight_total > 0 THEN
        floor(refunded_fee * cumulative / weight_total) -
        floor(refunded_fee * (cumulative - line_total) / weight_total) ELSE 0 END AS fee_refund
    FROM weighted w
), selected AS (
    SELECT * FROM lines
    WHERE (CAST(:ticket_type_id AS uuid) IS NULL OR ticket_type_id = :ticket_type_id)
)
"""

METRICS = """
 count(DISTINCT order_id)::bigint AS orders,
 coalesce(sum(quantity),0)::bigint AS tickets,
 coalesce(sum(unit_price_amount::numeric * quantity),0)::numeric AS gross_amount,
 coalesce(sum(discount_amount),0)::numeric AS discount_amount,
 coalesce(sum(fee),0)::numeric AS fee_amount,
 coalesce(sum(ticket_refund + fee_refund),0)::numeric AS refund_amount,
 coalesce(sum(ticket_refund),0)::numeric AS ticket_refund_amount,
 coalesce(sum(fee_refund),0)::numeric AS fee_refund_amount,
 coalesce(sum(line_total - ticket_refund),0)::numeric AS net_amount,
 coalesce(sum(line_total + fee - ticket_refund - fee_refund),0)::numeric AS net_collected_amount,
 coalesce(sum(line_total - ticket_refund),0)::numeric AS estimated_payout_amount
"""


async def parameters(session: AsyncSession, event_id: uuid.UUID, filters: ReportFilters):
    if filters.ticket_type_id is not None:
        exists = await session.scalar(
            select(TicketType.id).where(
                TicketType.id == filters.ticket_type_id, TicketType.event_id == event_id
            )
        )
        if exists is None:
            raise AppError(NOT_FOUND, "Ticket type not found for this event.", 404)
    return {"event_id": event_id, **filters.model_dump()}


def normalize(row):
    result = dict(row)
    for key, value in result.items():
        if key.endswith("amount") or key in {"orders", "tickets", "redemptions", "refunded_orders"}:
            result[key] = int(value or 0)
    result.update(currency="KZT", simulated=True)
    return result


INVENTORY = """
, all_inventory AS (
    SELECT coalesce(sum(quantity_total),0) AS total,
      coalesce(sum(quantity_sold),0) AS sold,
      coalesce(sum(quantity_reserved),0) AS reserved FROM ticket_types WHERE event_id=:event_id
), inventory AS (
    SELECT coalesce(sum(quantity_total),0) AS ticket_capacity,
      coalesce(sum(quantity_sold),0) AS sold,
      coalesce(sum(quantity_reserved),0) AS reserved FROM ticket_types WHERE event_id=:event_id
      AND (CAST(:ticket_type_id AS uuid) IS NULL OR id=:ticket_type_id)
), inventory_result AS (
    SELECT i.*, e.capacity AS event_capacity,
      least(i.ticket_capacity, coalesce(e.capacity, i.ticket_capacity)) AS capacity,
      greatest(0, least(i.ticket_capacity-i.sold-i.reserved,
        coalesce(e.capacity, a.total)-a.sold-a.reserved)) AS remaining
    FROM inventory i CROSS JOIN all_inventory a JOIN events e ON e.id=:event_id
), attendance AS (
    SELECT count(*) FILTER (WHERE t.status IN ('valid','checked_in')) AS registered,
      count(*) FILTER (WHERE t.status='checked_in') AS checked_in
    FROM tickets t JOIN order_items i ON i.id=t.order_item_id
    JOIN cohort o ON o.id=i.order_id WHERE t.event_id=:event_id
      AND (CAST(:ticket_type_id AS uuid) IS NULL OR t.ticket_type_id=:ticket_type_id)
)
"""


async def summary(session, event_id, filters):
    params = await parameters(session, event_id, filters)
    row = (
        (
            await session.execute(
                text(
                    BASE
                    + INVENTORY
                    + ", financial AS (SELECT "
                    + METRICS
                    + " FROM selected) SELECT f.*, i.*, a.*, a.registered-a.checked_in AS absent "
                    "FROM financial f CROSS JOIN inventory_result i CROSS JOIN attendance a"
                ),
                params,
            )
        )
        .mappings()
        .one()
    )
    result = normalize(row)
    result.update(
        event_id=event_id,
        percent_sold=round(100 * result["sold"] / result["capacity"], 2)
        if result["capacity"]
        else 0,
        check_in_percent=round(100 * result["checked_in"] / result["registered"], 2)
        if result["registered"]
        else 0,
    )
    return result


async def attendance(session, event_id, filters):
    params = await parameters(session, event_id, filters)
    row = (
        (await session.execute(text(BASE + INVENTORY + " SELECT * FROM attendance"), params))
        .mappings()
        .one()
    )
    result = dict(row)
    result.update(
        absent=result["registered"] - result["checked_in"],
        check_in_percent=round(100 * result["checked_in"] / result["registered"], 2)
        if result["registered"]
        else 0,
    )
    return result


def report_query(kind):
    if kind == "daily":
        return (
            BASE
            + ", result AS (SELECT (placed_at AT TIME ZONE 'UTC')::date AS day, "
            + METRICS
            + " FROM selected GROUP BY day)"
        )
    if kind == "ticket-types":
        return (
            BASE
            + ", totals AS (SELECT ticket_type_id, "
            + METRICS
            + " FROM selected GROUP BY ticket_type_id), result AS (SELECT t.id AS ticket_type_id, t.name AS ticket_type_name, f.orders, f.tickets, f.gross_amount, f.discount_amount, f.fee_amount, f.refund_amount, f.ticket_refund_amount, f.fee_refund_amount, f.net_amount, f.net_collected_amount, f.estimated_payout_amount FROM ticket_types t LEFT JOIN totals f ON f.ticket_type_id=t.id WHERE t.event_id=:event_id AND (CAST(:ticket_type_id AS uuid) IS NULL OR t.id=:ticket_type_id))"
        )
    # Current completed-order revenue and historical refund activity are kept separate.
    key = "campaign_id" if kind == "campaigns" else "promo_code_id"
    tables = (
        "campaigns c"
        if kind == "campaigns"
        else "promo_codes p JOIN campaigns c ON c.id=p.campaign_id"
    )
    identity = "c.id AS campaign_id, c.name AS campaign_name"
    if kind == "promo-codes":
        identity += ", p.id AS promo_code_id, p.code AS promo_code"
    join_key = "c.id" if kind == "campaigns" else "p.id"
    return (
        BASE
        + f"""
    , totals AS (SELECT {key}, {METRICS}, count(DISTINCT order_id) AS redemptions
      FROM selected WHERE status='completed' GROUP BY {key}),
    reversals AS (SELECT {key}, count(DISTINCT order_id) FILTER
      (WHERE ticket_refund + fee_refund > 0) AS refunded_orders,
      sum(ticket_refund + fee_refund) AS historical_refund_amount
      FROM selected GROUP BY {key}), result AS (
      SELECT {identity}, f.orders, f.tickets, f.gross_amount, f.discount_amount,
        f.fee_amount, f.refund_amount, f.ticket_refund_amount, f.fee_refund_amount,
        f.net_amount, f.net_collected_amount, f.estimated_payout_amount,
        coalesce(f.redemptions,0) AS redemptions, coalesce(r.refunded_orders,0) AS refunded_orders,
        coalesce(r.historical_refund_amount,0) AS historical_refund_amount
      FROM {tables} LEFT JOIN totals f ON f.{key}={join_key}
      LEFT JOIN reversals r ON r.{key}={join_key} WHERE c.event_id=:event_id)
    """
    )


SORTS = {
    "daily": "day",
    "ticket-types": "ticket_type_name, ticket_type_id",
    "campaigns": "campaign_name, campaign_id",
    "promo-codes": "promo_code, promo_code_id",
}


async def report(session, event_id, filters, kind, page):
    params = await parameters(session, event_id, filters)
    params.update(limit=page.limit, offset=page.offset)
    # Count and rows share one PostgreSQL snapshot, including out-of-range pages.
    query = (
        report_query(kind)
        + f"""
    , page AS (SELECT * FROM result ORDER BY {SORTS[kind]} LIMIT :limit OFFSET :offset)
    SELECT (SELECT count(*) FROM result) AS total,
      coalesce((SELECT jsonb_agg(to_jsonb(p) ORDER BY {SORTS[kind]}) FROM page p),'[]'::jsonb) AS items
    """
    )
    result = (await session.execute(text(query), params)).mappings().one()
    return [normalize(row) for row in result["items"]], result["total"]
