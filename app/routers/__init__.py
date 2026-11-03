"""Routers package containing API route endpoints."""

from app.routers.reports import router as reports_router
from app.routers.map_zones import router as map_zones_router
from app.routers.assistant import router as assistant_router

__all__ = ["reports_router", "map_zones_router", "assistant_router"]

