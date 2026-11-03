import math
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple
import numpy as np
from sklearn.cluster import DBSCAN

from app.core.config import settings
from app.models.incident import Incident, IncidentCategory, IncidentSeverity, IncidentStatus
from app.models.schemas import (
    GeoJSONFeature,
    GeoJSONGeometry,
    MapZoneFeatureCollection,
    PatrolRouteResponse,
    PatrolWayPoint,
)

EARTH_RADIUS_KM = 6371.0088


def haversine_distance_meters(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Calculates great-circle distance between two GPS coordinates in meters."""
    d_lat = math.radians(lat2 - lat1)
    d_lon = math.radians(lon2 - lon1)
    a = (
        math.sin(d_lat / 2.0) ** 2
        + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(d_lon / 2.0) ** 2
    )
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return EARTH_RADIUS_KM * 1000.0 * c


def create_circle_polygon(center_lng: float, center_lat: float, radius_meters: float, num_points: int = 24) -> List[List[float]]:
    """
    Generates a closed GeoJSON Polygon ring [[lng, lat], ...] around a center point.
    Coordinates strictly adhere to GeoJSON standard [longitude, latitude].
    """
    coords: List[List[float]] = []
    # Convert meters to angular distance in radians
    angular_dist = radius_meters / (EARTH_RADIUS_KM * 1000.0)
    lat_rad = math.radians(center_lat)
    lng_rad = math.radians(center_lng)

    for i in range(num_points):
        bearing = 2.0 * math.pi * i / num_points
        point_lat = math.asin(
            math.sin(lat_rad) * math.cos(angular_dist)
            + math.cos(lat_rad) * math.sin(angular_dist) * math.cos(bearing)
        )
        point_lng = lng_rad + math.atan2(
            math.sin(bearing) * math.sin(angular_dist) * math.cos(lat_rad),
            math.cos(angular_dist) - math.sin(lat_rad) * math.sin(point_lat),
        )
        coords.append([math.degrees(point_lng), math.degrees(point_lat)])

    # Close the ring
    coords.append(coords[0])
    return coords


class GeoEngineService:
    """
    Geospatial engine for Santa Cruz de la Sierra:
    - 2dsphere near-neighbor queries
    - Anti-spam and anti-duplication detection
    - Unsupervised DBSCAN density clustering for Crime / Danger Heatmaps
    - Dynamic patrol routing for police and neighborhood watches
    """

    async def check_duplicate_or_spam(
        self,
        longitude: float,
        latitude: float,
        category: IncidentCategory,
        proximity_meters: Optional[float] = None,
        window_minutes: Optional[int] = None,
    ) -> Optional[Incident]:
        """
        Runs a spatial $geoNear aggregation to find if an incident was already reported
        within `proximity_meters` in the last `window_minutes`.
        Prevents spam flooding and merges repeated notifications.
        """
        max_dist = proximity_meters or settings.SPAM_PROXIMITY_METERS
        win_mins = window_minutes or settings.SPAM_WINDOW_MINUTES
        cutoff_time = datetime.utcnow() - timedelta(minutes=win_mins)

        if hasattr(Incident, "get_motor_collection"):
            collection = Incident.get_motor_collection()
        else:
            collection = Incident.get_pymongo_collection()

        pipeline = [
            {
                "$geoNear": {
                    "near": {
                        "type": "Point",
                        "coordinates": [longitude, latitude],  # Strict [lng, lat]
                    },
                    "distanceField": "calculated_distance_meters",
                    "maxDistance": max_dist,
                    "spherical": True,
                    "query": {
                        "created_at": {"$gte": cutoff_time},
                        "category": category.value,
                        "status": {"$in": [IncidentStatus.ACTIVO.value, IncidentStatus.VERIFICADO.value]},
                    },
                }
            },
            {"$limit": 1},
        ]

        cursor = collection.aggregate(pipeline)
        docs = await cursor.to_list(length=1)

        if docs:
            duplicate_doc = docs[0]
            existing_incident = await Incident.get(str(duplicate_doc["_id"]))
            return existing_incident

        return None

    async def get_nearby_incidents(
        self,
        longitude: float,
        latitude: float,
        max_distance_meters: float = 1000.0,
        category: Optional[IncidentCategory] = None,
        limit: int = 50,
    ) -> List[Incident]:
        """Queries incidents indexed by 2dsphere sorted by distance from current location."""
        query_filter: Dict[str, Any] = {
            "location": {
                "$near": {
                    "$geometry": {
                        "type": "Point",
                        "coordinates": [longitude, latitude],
                    },
                    "$maxDistance": max_distance_meters,
                }
            },
            "status": {"$ne": IncidentStatus.DESCARTADO.value},
        }

        if category:
            query_filter["category"] = category.value

        incidents = await Incident.find(query_filter).limit(limit).to_list()
        return incidents

    async def compute_crime_clusters_and_zones(
        self,
        eps_km: Optional[float] = None,
        min_samples: Optional[int] = None,
    ) -> MapZoneFeatureCollection:
        """
        Executes DBSCAN clustering over Santa Cruz active incidents.
        Extracts spatial density hotspots and maps them into:
        - ZONA_ROJA (High severity, recurrent armed crime or lethal traffic accident)
        - ZONA_AMARILLA (Moderate risk or warning alerts)
        - ZONA_VERDE (Safe corridor or low risk area)
        Returns a valid GeoJSON FeatureCollection.
        """
        epsilon = eps_km or settings.DBSCAN_EPS_KM
        min_pts = min_samples or settings.DBSCAN_MIN_SAMPLES

        # Fetch recent non-discarded incidents
        all_incidents = await Incident.find(
            {"status": {"$ne": IncidentStatus.DESCARTADO.value}}
        ).to_list()

        features: List[GeoJSONFeature] = []

        if not all_incidents:
            return MapZoneFeatureCollection(
                type="FeatureCollection",
                features=[],
                metadata={
                    "total_incidents": 0,
                    "clusters_found": 0,
                    "timestamp": datetime.utcnow().isoformat(),
                    "city": "Santa Cruz de la Sierra, Bolivia",
                },
            )

        # DBSCAN haversine metric requires coordinates in [lat_radians, lon_radians]
        coords_rad = np.array(
            [[math.radians(inc.latitude), math.radians(inc.longitude)] for inc in all_incidents]
        )
        eps_rad = epsilon / EARTH_RADIUS_KM

        db = DBSCAN(eps=eps_rad, min_samples=min_pts, metric="haversine")
        labels = db.fit_predict(coords_rad)

        unique_labels = set(labels)
        cluster_count = sum(1 for label in unique_labels if label != -1)

        # Process each cluster
        for label in unique_labels:
            if label == -1:
                continue

            cluster_indices = [i for i, lbl in enumerate(labels) if lbl == label]
            cluster_incidents = [all_incidents[idx] for idx in cluster_indices]

            center_lat = float(np.mean([inc.latitude for inc in cluster_incidents]))
            center_lng = float(np.mean([inc.longitude for inc in cluster_incidents]))

            # Determine radius covering all points in cluster + 80m buffer
            max_dist_cluster = max(
                haversine_distance_meters(center_lat, center_lng, inc.latitude, inc.longitude)
                for inc in cluster_incidents
            )
            buffer_radius = max(max_dist_cluster + 80.0, 150.0)

            # Analyze cluster risk
            has_armed = any(inc.category == IncidentCategory.ASALTO_MANO_ARMADA for inc in cluster_incidents)
            has_critical = any(inc.severity == IncidentSeverity.CRITICO for inc in cluster_incidents)
            count = len(cluster_incidents)

            if has_armed or has_critical or count >= 5:
                zone_type = "ZONA_ROJA"
                color = "#E53935"
                risk_label = "Peligro Crítico - Alta Incidencia Delictiva"
                patrol_priority = "URGENTE"
            else:
                zone_type = "ZONA_AMARILLA"
                color = "#FDD835"
                risk_label = "Precaución - Incidentes Frecuentes / Tránsito"
                patrol_priority = "MODERADA"

            top_neighborhoods = list(
                {inc.neighborhood for inc in cluster_incidents if inc.neighborhood}
            )
            category_counts = {}
            for inc in cluster_incidents:
                category_counts[inc.category.value] = category_counts.get(inc.category.value, 0) + 1

            polygon_ring = create_circle_polygon(center_lng, center_lat, buffer_radius)

            feature = GeoJSONFeature(
                type="Feature",
                geometry=GeoJSONGeometry(
                    type="Polygon",
                    coordinates=[polygon_ring],
                ),
                properties={
                    "cluster_id": int(label),
                    "zone_type": zone_type,
                    "color": color,
                    "risk_label": risk_label,
                    "patrol_priority": patrol_priority,
                    "incident_count": count,
                    "centroid": [center_lng, center_lat],
                    "radius_meters": round(buffer_radius, 1),
                    "categories_breakdown": category_counts,
                    "neighborhoods": top_neighborhoods or ["Radio Urbano SCZ"],
                },
            )
            features.append(feature)

        # Include prominent quiet/safe reference zones (ZONAS VERDES)
        # e.g., verified areas or quiet residential spots
        safe_hubs = [
            {"name": "Parque Urbano Central", "lng": -63.1725, "lat": -17.7885},
            {"name": "Zona Equipetrol Norte (Corredor Seguro)", "lng": -63.1970, "lat": -17.7610},
            {"name": "Campus Universitario UAGRM", "lng": -63.1930, "lat": -17.7760},
        ]

        for idx, hub in enumerate(safe_hubs):
            # Verify no red zone overlaps within 500m
            is_close_to_cluster = False
            for f in features:
                c_lng, c_lat = f.properties["centroid"]
                if haversine_distance_meters(hub["lat"], hub["lng"], c_lat, c_lng) < 600.0:
                    is_close_to_cluster = True
                    break

            if not is_close_to_cluster:
                safe_poly = create_circle_polygon(hub["lng"], hub["lat"], 220.0)
                safe_feature = GeoJSONFeature(
                    type="Feature",
                    geometry=GeoJSONGeometry(type="Polygon", coordinates=[safe_poly]),
                    properties={
                        "cluster_id": 900 + idx,
                        "zone_type": "ZONA_VERDE",
                        "color": "#43A047",
                        "risk_label": "Zona Segura / Corredor Iluminado y Vigilado",
                        "patrol_priority": "PREVENTIVA",
                        "incident_count": 0,
                        "centroid": [hub["lng"], hub["lat"]],
                        "radius_meters": 220.0,
                        "neighborhoods": [hub["name"]],
                    },
                )
                features.append(safe_feature)

        return MapZoneFeatureCollection(
            type="FeatureCollection",
            features=features,
            metadata={
                "total_incidents_analyzed": len(all_incidents),
                "clusters_found": cluster_count,
                "city": "Santa Cruz de la Sierra, Bolivia",
                "timestamp": datetime.utcnow().isoformat(),
            },
        )

    async def generate_patrol_routes(self) -> PatrolRouteResponse:
        """
        Synthesizes active crime hotspots to build an optimized patrol circuit
        for Radio Patrulla 110 and Guardia Municipal de Santa Cruz.
        """
        zone_collection = await self.compute_crime_clusters_and_zones()
        red_zones = [
            f for f in zone_collection.features if f.properties.get("zone_type") == "ZONA_ROJA"
        ]
        yellow_zones = [
            f for f in zone_collection.features if f.properties.get("zone_type") == "ZONA_AMARILLA"
        ]

        # Prioritize Red Zones first, then Yellow Zones
        priority_clusters = red_zones + yellow_zones

        waypoints: List[PatrolWayPoint] = []
        coordinates_route: List[List[float]] = []

        if not priority_clusters:
            # Default preventive patrol route around key central avenues of Santa Cruz
            default_points = [
                (-17.7833, -63.1821, "Plaza 24 de Septiembre - Casco Viejo", "PREVENTIVO"),
                (-17.7712, -63.1802, "Monseñor Rivero / El Cristo", "PREVENTIVO"),
                (-17.7650, -63.1950, "Av. San Martín / Equipetrol", "PREVENTIVO"),
                (-17.7950, -63.1650, "Av. Brasil / Los Pozos", "PREVENTIVO"),
                (-17.8100, -63.1900, "La Ramada / Av. Grigotá", "PREVENTIVO"),
            ]
            for order, (lat, lng, name, rlevel) in enumerate(default_points, start=1):
                waypoints.append(
                    PatrolWayPoint(
                        order=order,
                        latitude=lat,
                        longitude=lng,
                        neighborhood=name,
                        risk_level=rlevel,
                        notes="Ronda preventiva disuasiva y monitoreo de alumbrado.",
                    )
                )
                coordinates_route.append([lng, lat])
        else:
            for order, cluster in enumerate(priority_clusters[:8], start=1):
                lng, lat = cluster.properties["centroid"]
                n_names = ", ".join(cluster.properties.get("neighborhoods", []))
                risk = cluster.properties.get("zone_type", "ZONA_AMARILLA")
                count = cluster.properties.get("incident_count", 1)
                waypoints.append(
                    PatrolWayPoint(
                        order=order,
                        latitude=lat,
                        longitude=lng,
                        neighborhood=n_names or "Santa Cruz",
                        risk_level=risk,
                        notes=f"Punto crítico con {count} denuncias recientes. Requiere baliza y verificación.",
                    )
                )
                coordinates_route.append([lng, lat])

        geojson_line = GeoJSONFeature(
            type="Feature",
            geometry=GeoJSONGeometry(
                type="LineString",
                coordinates=coordinates_route,
            ),
            properties={
                "route_name": "Circuito Alfa Centinela SCZ",
                "target_department": "Policía Departamental Santa Cruz / Guardia Municipal",
                "active_waypoints_count": len(waypoints),
            },
        )

        return PatrolRouteResponse(
            route_name="Circuito Alfa Centinela SCZ",
            target_sector="Anillos y Radiales Críticos de Santa Cruz",
            total_waypoints=len(waypoints),
            risk_summary=(
                f"Ruta generada cubriendo {len(red_zones)} focos rojos de alta prioridad "
                f"y {len(yellow_zones)} zonas de vigilancia moderada."
            ),
            waypoints=waypoints,
            geojson=geojson_line,
        )


geo_engine = GeoEngineService()

