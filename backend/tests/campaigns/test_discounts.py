import uuid

import pytest

from app.modules.campaigns.discounts import DiscountLine, calculate_discount
from app.modules.campaigns.models import DiscountType

A, B = uuid.uuid4(), uuid.uuid4()


@pytest.mark.parametrize(
    "kind,value,lines,applicable,expected",
    [
        (DiscountType.PERCENT, 15, [DiscountLine(A, 101, 3)], set(), (303, 303, 45, 258)),
        (
            DiscountType.PERCENT,
            50,
            [DiscountLine(A, 1, 1), DiscountLine(B, 1, 1)],
            set(),
            (2, 2, 1, 1),
        ),
        (
            DiscountType.PERCENT,
            25,
            [DiscountLine(A, 1000, 2), DiscountLine(B, 2000, 1)],
            {A},
            (4000, 2000, 500, 3500),
        ),
        (
            DiscountType.FIXED,
            10000,
            [DiscountLine(A, 1000, 2), DiscountLine(B, 2000, 1)],
            {A},
            (4000, 2000, 2000, 2000),
        ),
        (DiscountType.PERCENT, 100, [DiscountLine(A, 3000, 1)], set(), (3000, 3000, 3000, 0)),
        (DiscountType.FIXED, 500, [DiscountLine(A, 0, 2)], set(), (0, 0, 0, 0)),
        (DiscountType.FIXED, 500, [DiscountLine(A, 1000, 2)], {B}, (2000, 0, 0, 2000)),
        (
            DiscountType.PERCENT,
            99,
            [DiscountLine(A, 9_000_000_000_000_001, 1)],
            set(),
            (
                9_000_000_000_000_001,
                9_000_000_000_000_001,
                8_910_000_000_000_000,
                90_000_000_000_001,
            ),
        ),
    ],
)
def test_whole_tenge_calculation(kind, value, lines, applicable, expected):
    result = calculate_discount(kind, value, lines, applicable)
    assert (
        result.subtotal_amount,
        result.eligible_subtotal_amount,
        result.discount_amount,
        result.total_amount,
    ) == expected


@pytest.mark.parametrize(
    "kind,value,lines",
    [
        (DiscountType.PERCENT, 101, []),
        (DiscountType.FIXED, 0, []),
        (DiscountType.PERCENT, -1, []),
        (DiscountType.PERCENT, 10, [DiscountLine(A, -1, 1)]),
        (DiscountType.FIXED, 1, [DiscountLine(A, 1, 0)]),
    ],
)
def test_invalid_calculation_inputs(kind, value, lines):
    with pytest.raises(ValueError):
        calculate_discount(kind, value, lines, set())
