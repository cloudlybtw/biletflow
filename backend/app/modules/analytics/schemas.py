import uuid
from datetime import date
from typing import Literal

from pydantic import BaseModel


class FinancialMetrics(BaseModel):
    orders: int = 0
    tickets: int = 0
    gross_amount: int = 0
    discount_amount: int = 0
    fee_amount: int = 0
    refund_amount: int = 0
    ticket_refund_amount: int = 0
    fee_refund_amount: int = 0
    net_amount: int = 0
    net_collected_amount: int = 0
    estimated_payout_amount: int = 0
    currency: Literal["KZT"] = "KZT"
    simulated: Literal[True] = True


class InventoryMetrics(BaseModel):
    ticket_capacity: int
    event_capacity: int | None
    capacity: int
    sold: int
    reserved: int
    remaining: int
    percent_sold: float
    inventory_scope: Literal["current"] = "current"


class AttendanceOut(BaseModel):
    registered: int
    checked_in: int
    absent: int
    check_in_percent: float
    attendance_scope: Literal["current_status_in_order_cohort"] = "current_status_in_order_cohort"


class SummaryOut(FinancialMetrics, InventoryMetrics, AttendanceOut):
    event_id: uuid.UUID


class DailySalesOut(FinancialMetrics):
    day: date
    bucket_timezone: Literal["UTC"] = "UTC"


class TicketTypeSalesOut(FinancialMetrics):
    ticket_type_id: uuid.UUID
    ticket_type_name: str


class CampaignReportOut(FinancialMetrics):
    campaign_id: uuid.UUID
    campaign_name: str
    redemptions: int
    refunded_orders: int
    historical_refund_amount: int
    revenue_scope: Literal["completed_orders_only"] = "completed_orders_only"


class PromoReportOut(CampaignReportOut):
    promo_code_id: uuid.UUID
    promo_code: str
