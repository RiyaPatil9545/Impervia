from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.api.v1.router import api_router
from app.core.config import settings
from app.core.logging_config import logger, setup_logging
from app.db.session import engine
from app.middleware.error_handler import SafeErrorHandlerMiddleware
from app.middleware.request_context import RequestTimingMiddleware


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Setup safe logging
    setup_logging()
    logger.info(f"Starting {settings.APP_NAME} backend v{settings.APP_VERSION}")

    # Verify Aiven PostgreSQL database connectivity in read-only manner
    # CRITICAL: We NEVER execute Base.metadata.create_all() or destructive DDL on existing Aiven DB
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        logger.info("Successfully verified connection to Aiven PostgreSQL.")
    except Exception as exc:
        logger.error(f"PostgreSQL connection verification failed: {exc}")

    yield

    logger.info(f"Shutting down {settings.APP_NAME} backend.")


app = FastAPI(
    title=settings.APP_NAME,
    description=(
        "Impervia: A Privacy-Aware Academic Assistant backend protecting student "
        "privacy before academic questions are processed by AI models."
    ),
    version=settings.APP_VERSION,
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# Middleware
app.add_middleware(RequestTimingMiddleware)
app.add_middleware(SafeErrorHandlerMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API Routers
app.include_router(api_router, prefix=settings.API_V1_STR)


@app.get("/", tags=["Root"])
def root():
    return {
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "description": "Privacy-aware academic assistant backend",
        "status": "online",
        "docs_url": "/docs",
        "health_check": f"{settings.API_V1_STR}/health",
    }
