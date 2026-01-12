"""API routers."""

from .cards import router as cards_router
from .images import router as images_router
from .inventory import router as inventory_router
from .labels import router as labels_router
from .portfolio import router as portfolio_router
from .search import router as search_router
from .sets import router as sets_router
from .settings import router as settings_router
from .vault import router as vault_router

__all__ = [
    "cards_router",
    "images_router",
    "inventory_router",
    "labels_router",
    "portfolio_router",
    "search_router",
    "sets_router",
    "settings_router",
    "vault_router",
]
