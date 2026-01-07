"""FastAPI application entry point."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings
from .routers import cards_router, images_router, inventory_router, labels_router, sets_router
from .services import get_odoo_service


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan - connect to Odoo on startup."""
    settings = get_settings()
    odoo = get_odoo_service()

    print(f"🔌 Connecting to Odoo at {settings.odoo_url}...")
    try:
        await odoo.connect()
        print("✅ Odoo connection established")
    except Exception as e:
        print(f"⚠️  Odoo connection failed: {e}")
        print("   Server will retry on first request")

    yield

    print("👋 Shutting down...")


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
    )

    # CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Include routers
    app.include_router(cards_router, prefix="/api")
    app.include_router(inventory_router, prefix="/api")
    app.include_router(images_router, prefix="/api")
    app.include_router(labels_router, prefix="/api")
    app.include_router(sets_router, prefix="/api")

    @app.get("/api/health")
    async def health_check():
        """Health check endpoint."""
        odoo = get_odoo_service()
        odoo_connected = odoo._connected

        return {
            "status": "healthy",
            "odoo_connected": odoo_connected,
            "version": "2.0.0",
        }

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
