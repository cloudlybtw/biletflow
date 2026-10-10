from decimal import Decimal

import pytest

from app.core.errors import AppError
from app.modules.orders.pricing import MAX_AMOUNT, allocate_discount, processing_fee


@pytest.mark.parametrize(
    "subtotals,eligible,discount,expected",
    [
        ([101, 101, 101], [True, True, True], 45, [15, 15, 15]),
        ([1] * 100, [True] * 100, 99, [1] * 99 + [0]),
        ([300, 2000], [True, False], 300, [300, 0]),
        ([0, 100], [True, True], 1, [0, 1]),
        ([0, 0], [True, False], 0, [0, 0]),
    ],
)
def test_line_allocation_preserves_whole_order_discount(subtotals, eligible, discount, expected):
    assert allocate_discount(subtotals, eligible, discount) == expected


def test_processing_fee_uses_whole_tenge_decimal_arithmetic():
    assert processing_fee(1700, Decimal("2.5")) == 42
    assert processing_fee(9_000_000_000_000_001, Decimal("1")) == 90_000_000_000_000
    # Preserve a configured high-precision percentage just below 100%; the
    # default Decimal context could round it up before flooring the fee.
    assert processing_fee(10**18, Decimal("99." + "9" * 40)) == 10**18 - 1
    with pytest.raises(AppError, match="supported amount"):
        processing_fee(MAX_AMOUNT, Decimal("100"))
