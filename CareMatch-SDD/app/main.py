import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1 import assessments, audit, auth, caregivers, health, metrics, patients, trials
from app.config import get_settings
from app.db import repositories as repo
from app.db.database import SessionLocal, init_db
from app.middleware.audit import AuditMiddleware
from app.middleware.error import install_error_handlers
from app.middleware.metrics import MetricsMiddleware
from app.middleware.ratelimit import RateLimitMiddleware
from app.services.security import hash_password

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("carematch")


def seed_users() -> None:
    db = SessionLocal()
    try:
        if repo.count_users(db) > 0:
            return
        settings = get_settings()
        users = [
            (settings.seed_admin_username, settings.seed_admin_password, "ADMINISTRATOR"),
            (settings.seed_coordinator_username, settings.seed_coordinator_password, "COORDINATOR"),
            (settings.seed_provider_username, settings.seed_provider_password, "PROVIDER"),
            (settings.seed_auditor_username, settings.seed_auditor_password, "AUDITOR"),
        ]
        for username, password, role in users:
            repo.create_user(
                db,
                username=username,
                password_hash=hash_password(password),
                role=role,
                is_active=True,
            )
        logger.info("Seeded %d default users", len(users))
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    seed_users()
    logger.info("CareMatch API started (env=%s)", get_settings().env)
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="CareMatch API",
        version="1.0.0",
        description=(
            "Clinical trial patient eligibility screening with explainable, "
            "evidence-backed AI recommendations and human-in-the-loop review."
        ),
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
    )

    app.add_middleware(
        CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"]
    )
    app.add_middleware(RateLimitMiddleware)
    app.add_middleware(AuditMiddleware)
    app.add_middleware(MetricsMiddleware)

    install_error_handlers(app)

    app.include_router(health.router, tags=["health"])
    api_prefix = settings.api_prefix
    app.include_router(auth.router, prefix=api_prefix)
    app.include_router(patients.router, prefix=api_prefix)
    app.include_router(trials.router, prefix=api_prefix)
    app.include_router(caregivers.router, prefix=api_prefix)
    app.include_router(assessments.router, prefix=api_prefix)
    app.include_router(metrics.router, prefix=api_prefix)
    app.include_router(audit.router, prefix=api_prefix)

    return app


app = create_app()
