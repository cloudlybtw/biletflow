from fastapi import FastAPI

import app.db.models  # noqa: F401  (registers every mapper)
from app.core.errors import register_exception_handlers
from app.core.health import router as health_router
from app.modules.activation.router import router as activation_router
from app.modules.admin.router import router as admin_router
from app.modules.auth.router import router as auth_router
from app.modules.campaigns.router import router as campaigns_router
from app.modules.events.router import router as events_router
from app.modules.orders.router import router as orders_router
from app.modules.organizers.router import router as organizers_router
from app.modules.payments.router import router as payments_router
from app.modules.tickets.router import router as tickets_router
from app.modules.users.router import router as users_router
from app.modules.venues.router import router as venues_router


def create_app() -> FastAPI:
    app = FastAPI(title="BiletFlow API", version="0.1.0")
    register_exception_handlers(app)
    app.include_router(health_router, prefix="/api/v1")
    app.include_router(auth_router, prefix="/api/v1")
    app.include_router(users_router, prefix="/api/v1")
    app.include_router(organizers_router, prefix="/api/v1")
    app.include_router(events_router, prefix="/api/v1")
    app.include_router(venues_router, prefix="/api/v1")
    app.include_router(campaigns_router, prefix="/api/v1")
    app.include_router(orders_router, prefix="/api/v1")
    app.include_router(payments_router, prefix="/api/v1")
    app.include_router(tickets_router, prefix="/api/v1")
    app.include_router(activation_router, prefix="/api/v1")
    app.include_router(admin_router, prefix="/api/v1")
    return app


app = create_app()
