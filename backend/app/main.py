import asyncio
from contextlib import asynccontextmanager, suppress

from fastapi import FastAPI

import app.db.models  # noqa: F401  (registers every mapper)
from app.core.errors import register_exception_handlers
from app.core.health import router as health_router
from app.db.session import AsyncSessionLocal, engine
from app.jobs.expire_orders import run as run_expiry
from app.modules.activation.router import router as activation_router
from app.modules.admin.operations_router import router as admin_operations_router
from app.modules.admin.router import router as admin_router
from app.modules.analytics.router import router as analytics_router
from app.modules.auth.router import router as auth_router
from app.modules.campaigns.router import router as campaigns_router
from app.modules.checkin.router import router as checkin_router
from app.modules.events.router import router as events_router
from app.modules.history.router import router as history_router
from app.modules.notifications.router import router as notifications_router
from app.modules.orders.router import router as orders_router
from app.modules.organizers.router import router as organizers_router
from app.modules.payments.router import router as payments_router
from app.modules.refunds.router import router as refunds_router
from app.modules.support.router import router as support_router
from app.modules.tickets.router import router as tickets_router
from app.modules.users.router import router as users_router
from app.modules.venues.router import router as venues_router


def create_app(*, session_factory=AsyncSessionLocal) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        task = asyncio.create_task(
            run_expiry(once=False, interval_seconds=30, session_factory=session_factory),
            name="biletflow-background-jobs",
        )
        app.state.background_task = task
        try:
            yield
        finally:
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task
            if session_factory is AsyncSessionLocal:
                await engine.dispose()

    app = FastAPI(title="BiletFlow API", version="0.1.0", lifespan=lifespan)
    register_exception_handlers(app)
    app.include_router(health_router, prefix="/api/v1")
    app.include_router(auth_router, prefix="/api/v1")
    app.include_router(users_router, prefix="/api/v1")
    app.include_router(organizers_router, prefix="/api/v1")
    app.include_router(events_router, prefix="/api/v1")
    app.include_router(notifications_router, prefix="/api/v1")
    app.include_router(venues_router, prefix="/api/v1")
    app.include_router(campaigns_router, prefix="/api/v1")
    app.include_router(orders_router, prefix="/api/v1")
    app.include_router(payments_router, prefix="/api/v1")
    app.include_router(refunds_router, prefix="/api/v1")
    app.include_router(support_router, prefix="/api/v1")
    app.include_router(tickets_router, prefix="/api/v1")
    app.include_router(checkin_router, prefix="/api/v1")
    app.include_router(activation_router, prefix="/api/v1")
    app.include_router(admin_router, prefix="/api/v1")
    app.include_router(admin_operations_router, prefix="/api/v1")
    app.include_router(analytics_router, prefix="/api/v1")
    app.include_router(history_router, prefix="/api/v1")
    return app


app = create_app()
