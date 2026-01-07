"""API routers."""

from .cards import router as cards_router
from .inventory import router as inventory_router
from .images import router as images_router
from .labels import router as labels_router
from .sets import router as sets_router

__all__ = ["cards_router", "inventory_router", "images_router", "labels_router", "sets_router"]

