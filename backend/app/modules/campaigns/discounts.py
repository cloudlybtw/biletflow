from dataclasses import dataclass
from uuid import UUID

from app.modules.campaigns.models import DiscountType


@dataclass(frozen=True)
class DiscountLine:
    ticket_type_id: UUID
    unit_price_amount: int
    quantity: int


@dataclass(frozen=True)
class DiscountAmounts:
    subtotal_amount: int
    eligible_subtotal_amount: int
    discount_amount: int

    @property
    def total_amount(self) -> int:
        return self.subtotal_amount - self.discount_amount


def calculate_discount(
    discount_type: DiscountType,
    discount_value: int,
    lines: list[DiscountLine],
    applicable_ticket_type_ids: set[UUID] | frozenset[UUID],
) -> DiscountAmounts:
    """Whole tenge: floor percent once on eligible subtotal; cap fixed discount.

    Empty applicability means all ticket types. No database access, reservations,
    fees or redemption mutations; checkout must apply this inside its transaction.
    """
    if discount_value <= 0 or (discount_type == DiscountType.PERCENT and discount_value > 100):
        raise ValueError("Invalid discount value.")
    if discount_type not in {DiscountType.PERCENT, DiscountType.FIXED}:
        raise ValueError("Invalid discount type.")
    if any(line.unit_price_amount < 0 or line.quantity <= 0 for line in lines):
        raise ValueError("Invalid cart line.")
    subtotal = sum(line.unit_price_amount * line.quantity for line in lines)
    eligible = sum(
        line.unit_price_amount * line.quantity
        for line in lines
        if not applicable_ticket_type_ids or line.ticket_type_id in applicable_ticket_type_ids
    )
    amount = (
        eligible * discount_value // 100
        if discount_type == DiscountType.PERCENT
        else min(discount_value, eligible)
    )
    return DiscountAmounts(subtotal, eligible, amount)
