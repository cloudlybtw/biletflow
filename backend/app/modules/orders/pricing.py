from decimal import ROUND_FLOOR, Decimal, localcontext

from app.core.errors import AppError

MAX_AMOUNT = 9_223_372_036_854_775_807


def processing_fee(amount: int, percent: Decimal) -> int:
    # Integer/Decimal arithmetic preserves whole-tenge amounts without float loss.
    with localcontext() as context:
        context.prec = max(50, len(str(amount)) + len(percent.as_tuple().digits) + 2)
        fee = int((Decimal(amount) * percent / 100).to_integral_value(rounding=ROUND_FLOOR))
    if amount > MAX_AMOUNT or amount + fee > MAX_AMOUNT:
        raise AppError("CART_TOTAL_TOO_LARGE", "Cart total exceeds the supported amount.", 422)
    return fee


def allocate_discount(subtotals: list[int], eligible: list[bool], discount: int) -> list[int]:
    """Largest-remainder allocation keeps line totals consistent with the order.

    This apportions the already-rounded order discount; it never recalculates
    rounding per line and never discounts an ineligible line.
    """
    if len(subtotals) != len(eligible) or any(amount < 0 for amount in subtotals):
        raise ValueError("Invalid line subtotals.")
    total = sum(amount for amount, applies in zip(subtotals, eligible, strict=True) if applies)
    if not 0 <= discount <= total:
        raise ValueError("Discount exceeds eligible subtotal.")
    result = [0] * len(subtotals)
    if not total:
        return result
    indices = [i for i, applies in enumerate(eligible) if applies and subtotals[i] > 0]
    for i in indices:
        result[i] = subtotals[i] * discount // total
    remainder = discount - sum(result)
    ranked = sorted(indices, key=lambda i: (-(subtotals[i] * discount % total), i))
    for i in ranked[:remainder]:
        result[i] += 1
    return result
