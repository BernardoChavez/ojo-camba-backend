from typing import Optional
from fastapi import APIRouter, Query

from app.models.schemas import MapZoneFeatureCollection, PatrolRouteResponse
from app.services.geo_engine import geo_engine

router = APIRouter(prefix="/map", tags=["Mapeo GIS y Patrullaje"])


@router.get(
    "/zones",
    response_model=MapZoneFeatureCollection,
    summary="Obtener capas GeoJSON de Zonas Rojas, Amarillas y Verdes (DBSCAN)",
)
async def get_map_zones(
    eps_km: Optional[float] = Query(
        None,
        ge=0.1,
        le=5.0,
        description="Radio epsilon en kilómetros para clustering DBSCAN (default: 0.4 km)",
    ),
    min_samples: Optional[int] = Query(
        None,
        ge=2,
        le=20,
        description="Mínimo de reportes para consolidar un cluster delictivo (default: 3)",
    ),
):
    """
    Retorna una FeatureCollection GeoJSON estándar con los polígonos de calor:
    - **ZONA_ROJA (#E53935):** Foco crítico con asaltos armados o alta densidad criminal.
    - **ZONA_AMARILLA (#FDD835):** Foco moderado de robos o incidentes viales.
    - **ZONA_VERDE (#43A047):** Corredores tranquilos, seguros y patrullados.

    Compatible de forma nativa con Leaflet, Mapbox GL JS, Google Maps y OpenLayers.
    """
    return await geo_engine.compute_crime_clusters_and_zones(
        eps_km=eps_km,
        min_samples=min_samples,
    )


@router.get(
    "/patrol-routes",
    response_model=PatrolRouteResponse,
    summary="Generar ruta de patrullaje preventivo optimizada para Radio Patrulla 110",
)
async def get_patrol_routes():
    """
    Calcula una ruta dinámica que conecta los puntos críticos con mayor riesgo delictivo
    en los anillos y radiales de Santa Cruz de la Sierra.
    Retorna la lista ordenada de waypoints y el GeoJSON LineString del recorrido.
    """
    return await geo_engine.generate_patrol_routes()

