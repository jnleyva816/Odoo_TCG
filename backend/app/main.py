"""FastAPI application entry point."""

import json
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Response, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware

from .auth.odoo_auth import get_odoo_auth_service
from .auth.router import router as auth_router
from .config import get_settings
from .middleware import (
    RateLimitMiddleware,
    RequestIDMiddleware,
    SecurityHeadersMiddleware,
)
from .routers import (
    cards_router,
    images_router,
    inventory_router,
    labels_router,
    portfolio_router,
    search_router,
    sets_router,
    settings_router,
    vault_router,
)
from .services import get_odoo_service


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan - connect to Odoo on startup, cleanup on shutdown."""
    settings = get_settings()
    odoo = get_odoo_service()
    auth = get_odoo_auth_service()

    # Startup
    print("🚀 Starting TCG Inventory API...")
    print("🔐 Initializing Odoo authentication...")
    await auth.initialize()

    print(f"🔌 Connecting to Odoo at {settings.odoo_url}...")
    try:
        await odoo.connect()
        print("✅ Odoo connection established")
        print("   Users authenticate directly with Odoo credentials")
    except Exception as e:
        print(f"⚠️  Odoo connection failed: {e}")
        print("   Server will retry on first request")

    yield

    # Shutdown
    print("👋 Shutting down gracefully...")
    # Add cleanup tasks here (close connections, flush logs, etc.)
    print("✅ Shutdown complete")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    settings = get_settings()

    app = FastAPI(
        title="TCG Inventory API",
        description="API for managing Pokemon TCG card inventory with Odoo integration",
        version="2.0.0",
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
        # Disable trailing slash redirects - they lose Authorization headers
        redirect_slashes=False,
    )

    # Security middleware (applied in reverse order)
    app.add_middleware(SecurityHeadersMiddleware, debug=settings.debug)
    app.add_middleware(
        RateLimitMiddleware,
        redis_url=settings.redis_url,
        requests_per_minute=60,
        burst_size=10,
    )
    app.add_middleware(RequestIDMiddleware)

    # Compression middleware (gzip responses > 500 bytes)
    app.add_middleware(GZipMiddleware, minimum_size=500)

    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Auth router (public)
    app.include_router(auth_router, prefix="/api")

    # Protected routers - require authentication
    from .auth.dependencies import get_current_user

    app.include_router(
        cards_router,
        prefix="/api",
        dependencies=[Depends(get_current_user)],
    )
    app.include_router(
        inventory_router,
        prefix="/api",
        dependencies=[Depends(get_current_user)],
    )
    app.include_router(
        images_router,
        prefix="/api",
        dependencies=[Depends(get_current_user)],
    )
    app.include_router(
        labels_router,
        prefix="/api",
        dependencies=[Depends(get_current_user)],
    )
    app.include_router(
        sets_router,
        prefix="/api",
        dependencies=[Depends(get_current_user)],
    )
    app.include_router(
        search_router,
        prefix="/api",
        dependencies=[Depends(get_current_user)],
    )

    # Premium feature routers (feature flag checked in router)
    app.include_router(
        portfolio_router,
        prefix="/api",
        dependencies=[Depends(get_current_user)],
    )
    # Vault has mixed auth - owner endpoints require auth, public share doesn't
    app.include_router(vault_router, prefix="/api")

    # Settings router - mixed auth (features endpoint is public)
    app.include_router(settings_router, prefix="/api")

    @app.get("/api/health")
    async def health_check():
        """Health check endpoint - liveness probe.

        Returns 200 if application is running.
        Use for container liveness checks.
        """
        return {
            "status": "healthy",
            "version": "2.0.0",
        }

    @app.get("/api/health/ready")
    async def readiness_check():
        """Readiness check endpoint.

        Returns 200 if application is ready to serve traffic.
        Checks dependencies (Odoo connection).
        Use for Kubernetes readiness probes.
        """
        odoo = get_odoo_service()
        odoo_connected = odoo._connected

        if not odoo_connected:
            error_response = {"status": "not_ready", "reason": "Odoo not connected"}
            return Response(
                content=json.dumps(error_response),
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                media_type="application/json",
            )

        return {
            "status": "ready",
            "version": "2.0.0",
            "dependencies": {
                "odoo": "connected",
            },
        }

    @app.get("/api/features")
    async def get_features():
        """Get enabled features (public endpoint for frontend).

        Fetches from Redis (admin-configurable) with fallback to env vars.
        """
        from .services.settings import get_settings_service

        service = get_settings_service()
        features = await service.get_features()
        return features.model_dump()

    @app.get("/")
    async def root():
        """Root endpoint - redirect to docs."""
        return {
            "message": "TCG Inventory API",
            "docs": "/docs",
            "openapi": "/openapi.json",
        }

    return app


# Create app instance
app = create_app()


if __name__ == "__main__":
    import uvicorn

    settings = get_settings()
    uvicorn.run(
        "app.main:app",
        host=settings.server_host,
        port=settings.server_port,
        reload=settings.debug,
    )
