"""Run with `uv run python -m app.jobs.expire_orders [--once]`.

Started by the API lifespan; each pass expires reservations and delivers mail.
The CLI also supports a one-off pass over the same jobs.
Concurrent workers skip busy events and re-check the order state under locks.
"""

import argparse
import asyncio
import contextlib
import logging

import app.db.models  # noqa: F401 (register every mapper for the standalone worker)
from app.db.session import AsyncSessionLocal, engine
from app.jobs.send_notifications import deliver_batch
from app.modules.orders.service import sweep_expired

logger = logging.getLogger(__name__)


async def run(*, once: bool, interval_seconds: int, session_factory=AsyncSessionLocal) -> None:
    while True:
        try:
            async with session_factory() as session:
                count = await sweep_expired(session)
                logger.info("Expired %s orders", count)
        except Exception:
            if once:
                raise
            logger.exception("Order expiry pass failed; retrying on the next interval")
        try:
            count = await deliver_batch(session_factory=session_factory)
            logger.info("Sent %s notifications", count)
        except Exception:
            if once:
                raise
            logger.exception("Notification pass failed; retrying on the next interval")
        if once:
            return
        await asyncio.sleep(interval_seconds)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Expire BiletFlow reservations and deliver queued email"
    )
    parser.add_argument("--once", action="store_true", help="Run one batch and exit")
    parser.add_argument("--interval-seconds", type=int, default=30)
    args = parser.parse_args()
    if args.interval_seconds < 1:
        parser.error("--interval-seconds must be positive")
    logging.basicConfig(level=logging.INFO)
    with contextlib.suppress(KeyboardInterrupt):
        asyncio.run(run_cli(once=args.once, interval_seconds=args.interval_seconds))


async def run_cli(*, once: bool, interval_seconds: int) -> None:
    try:
        await run(once=once, interval_seconds=interval_seconds)
    finally:
        await engine.dispose()


if __name__ == "__main__":
    main()
