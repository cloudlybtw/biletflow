import pytest

from app.scripts.reset_demo import validate_target


@pytest.mark.parametrize(
    "name,confirmation",
    [("biletflow", "biletflow"), ("production", "production"), ("biletflow_demo", "wrong")],
)
def test_reset_refuses_non_demo_database_or_wrong_confirmation(name, confirmation):
    with pytest.raises(ValueError):
        validate_target(f"postgresql+asyncpg://user:pass@localhost/{name}", confirmation)


def test_reset_accepts_only_exact_demo_confirmation():
    assert (
        validate_target("postgresql+asyncpg://user:pass@localhost/biletflow_demo", "biletflow_demo")
        == "biletflow_demo"
    )
