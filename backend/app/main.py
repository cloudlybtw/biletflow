from fastapi import FastAPI

from app.core.errors import register_exception_handlers
from app.core.health import router as health_router


def create_app() -> FastAPI:
    app = FastAPI(title="BiletFlow API", version="0.1.0")
    register_exception_handlers(app)
    app.include_router(health_router, prefix="/api/v1")
    return app


app = create_app()
