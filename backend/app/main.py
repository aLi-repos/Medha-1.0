from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes.agent import router as agent_router
from app.api.routes.auth import router as auth_router
from app.api.routes.chat import router as chat_router
from app.api.routes.demo import router as demo_router
from app.api.routes.environment import router as environment_router
from app.api.routes.health import router as health_router
from app.api.routes.knowledge import router as knowledge_router
from app.api.routes.model_router import router as model_router
from app.api.routes.sandbox import router as sandbox_router
from app.api.routes.tasks import router as tasks_router
from app.api.routes.analysis import router as analysis_router
from app.api.routes.security_mode import router as security_mode_router
from app.api.routes.supervision import router as supervision_router
from app.api.routes.verifier import router as verifier_router
from app.core.config import settings
from app.core.database import init_db, SessionLocal
from app.services.user_service import user_service


def create_app() -> FastAPI:
    """Create the MEDHA API application.

    Configures CORS for the local React/Vite frontend and registers
    all MEDHA API routers.
    """
    application = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
    )

    # Allow the local React/Vite frontend to communicate with
    # the FastAPI backend during development.
    application.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:5173",
            "http://127.0.0.1:5173",
            "null",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @application.on_event("startup")
    def _on_startup() -> None:
        init_db()
        db = SessionLocal()
        try:
            user_service.seed_demo_users(db)
        finally:
            db.close()

    @application.get("/")
    def root():
        return {
            "service": settings.app_name,
            "version": settings.app_version,
            "status": "running",
            "docs": "/docs",
        }

    application.include_router(health_router)
    application.include_router(environment_router, prefix="/api")
    # Public evaluator demo — synthetic scenario only, no auth, no DB writes.
    application.include_router(demo_router, prefix="/api")
    application.include_router(auth_router, prefix="/api")
    application.include_router(tasks_router, prefix="/api")
    application.include_router(chat_router, prefix="/api")
    application.include_router(knowledge_router, prefix="/api")
    application.include_router(model_router, prefix="/api")
    application.include_router(agent_router, prefix="/api")
    application.include_router(sandbox_router, prefix="/api")
    application.include_router(verifier_router, prefix="/api")
    application.include_router(analysis_router, prefix="/api")
    application.include_router(security_mode_router, prefix="/api")
    application.include_router(supervision_router, prefix="/api")

    return application


app = create_app()