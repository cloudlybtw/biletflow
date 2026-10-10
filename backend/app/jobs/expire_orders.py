"""Run with `uv run python -m app.jobs.expire_orders [--once]`.

Independent of the API process, so expiry still runs when there are no requests.
Concurrent workers skip busy events and re-check the order state under locks.
"""

import argparse
import asyncio
import contextlib
import logging

import app.db.models  # noqa: F401 (register every mapper for the standalone worker)
from app.db.session import AsyncSessionLocal, engine
from app.modules.orders.service import sweep_expired

logger = logging.getLogger(__name__)


async def run(*, once: bool, interval_seconds: int) -> None:
    try:
        while True:
            try:
                async with AsyncSessionLocal() as session:
                    count = await sweep_expired(session)
                    logger.info("Expired %s orders", count)
            except Exception:
                if once:
                    raise
                logger.exception("Order expiry pass failed; retrying on the next interval")
            if once:
                return
            await asyncio.sleep(interval_seconds)
    finally:
        await engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description="Release expired BiletFlow order reservations")
    parser.add_argument("--once", action="store_true", help="Run one batch and exit")
    parser.add_argument("--interval-seconds", type=int, default=60)
    args = parser.parse_args()
    if args.interval_seconds < 1:
        parser.error("--interval-seconds must be positive")
    logging.basicConfig(level=logging.INFO)
    with contextlib.suppress(KeyboardInterrupt):
        asyncio.run(run(once=args.once, interval_seconds=args.interval_seconds))


if __name__ == "__main__":
    main()
