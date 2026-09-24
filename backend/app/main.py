from fastapi import FastAPI

import app.db.models  # noqa: F401  (registers every mapper)
from app.core.errors import register_exception_handlers
from app.core.health import router as health_router
from app.modules.auth.router import router as auth_router
from app.modules.organizers.router import router as organizers_router
from app.modules.users.router import router as users_router


def create_app() -> FastAPI:
    app = FastAPI(title="BiletFlow API", version="0.1.0")
    register_exception_handlers(app)
    app.include_router(health_router, prefix="/api/v1")
    app.include_router(auth_router, prefix="/api/v1")
    app.include_router(users_router, prefix="/api/v1")
    app.include_router(organizers_router, prefix="/api/v1")
    return app


app = create_app()
