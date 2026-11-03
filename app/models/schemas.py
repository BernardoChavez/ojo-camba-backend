from datetime import datetime
from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, Field, field_validator

from app.models.incident import GeoJSONPoint, IncidentCategory, IncidentSeverity, IncidentStatus


class GeoPoint(BaseModel):
    """User input representation for GPS coordinates."""

    latitude: float = Field(..., description="Latitud en grados decimales (ej. -17.7833)")
    longitude: float = Field(..., description="Longitud en grados decimales (ej. -63.1821)")

    @field_validator("latitude")
    @classmethod
    def validate_latitude(cls, v: float) -> float:
        if not (-90.0 <= v <= 90.0):
            raise ValueError("Latitud inválida, debe estar entre -90 y 90.")
        return v

    @field_validator("longitude")
    @classmethod
    def validate_longitude(cls, v: float) -> float:
        if not (-180.0 <= v <= 180.0):
            raise ValueError("Longitud inválida, debe estar entre -180 y 180.")
        return v


class IncidentCreateRequest(BaseModel):
    """Payload to report a new security or road incident in Santa Cruz."""

    title: str = Field(..., min_length=5, max_length=150, example="Robo de celular en parada de micro")
    description: str = Field(
        ...,
        min_length=10,
        max_length=1000,
        example="Dos sujetos en motocicleta negra sin placa arrebataron mochila sobre el 2do anillo.",
    )
    category: IncidentCategory = Field(..., example=IncidentCategory.ROBO)
    severity: Optional[IncidentSeverity] = Field(default=None, description="Si no se envía, la IA lo evaluará.")
    latitude: float = Field(..., example=-17.7833)
    longitude: float = Field(..., example=-63.1821)
    neighborhood: Optional[str] = Field(None, example="Equipetrol")
    anillo: Optional[int] = Field(None, ge=1, le=10, example=2)
    reporter_alias: Optional[str] = Field("Vecino Alerta", example="Vecino Alerta")
    photo_base64: Optional[str] = Field(None, description="Cadena Base64 de la foto de evidencia tomada con la cámara")

    def to_geojson_point(self) -> GeoJSONPoint:
        # Strict GeoJSON ordering: [longitude, latitude]
        return GeoJSONPoint(type="Point", coordinates=[self.longitude, self.latitude])


class IncidentResponse(BaseModel):
    """Serialized representation of an incident record."""

    id: str
    title: str
    description: str
    category: IncidentCategory
    severity: IncidentSeverity
    status: IncidentStatus
    location: GeoJSONPoint
    latitude: float
    longitude: float
    neighborhood: Optional[str] = None
    anillo: Optional[int] = None
    reporter_alias: Optional[str] = None
    confirmations_count: int
    ai_triage: Optional[Dict[str, Any]] = None
    photo_base64: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class NearbyQueryRequest(BaseModel):
    """Query parameters for spatial proximity search."""

    latitude: float
    longitude: float
    max_distance_meters: float = Field(default=1000.0, ge=10.0, le=50000.0)
    category: Optional[IncidentCategory] = None
    limit: int = Field(default=50, ge=1, le=200)


class ConfirmReportResponse(BaseModel):
    """Response when a neighbor verifies or confirms an ongoing incident."""

    incident_id: str
    confirmations_count: int
    status: IncidentStatus
    message: str


# ==========================================
# GeoJSON FeatureCollection Schemas for Map
# ==========================================

class GeoJSONGeometry(BaseModel):
    type: Literal["Point", "Polygon", "MultiPolygon", "LineString"]
    coordinates: Any


class GeoJSONFeature(BaseModel):
    type: Literal["Feature"] = "Feature"
    geometry: GeoJSONGeometry
    properties: Dict[str, Any]


class MapZoneFeatureCollection(BaseModel):
    type: Literal["FeatureCollection"] = "FeatureCollection"
    features: List[GeoJSONFeature]
    metadata: Dict[str, Any]


class PatrolWayPoint(BaseModel):
    order: int
    latitude: float
    longitude: float
    neighborhood: str
    risk_level: str
    notes: str


class PatrolRouteResponse(BaseModel):
    route_name: str
    target_sector: str
    total_waypoints: int
    risk_summary: str
    waypoints: List[PatrolWayPoint]
    geojson: GeoJSONFeature


# ==========================================
# Conversational Assistant Schemas
# ==========================================

class ChatMessage(BaseModel):
    role: Literal["user", "assistant", "system"]
    content: str


class AssistantChatRequest(BaseModel):
    message: str = Field(..., min_length=2, max_length=2000)
    latitude: Optional[float] = Field(None, example=-17.7833)
    longitude: Optional[float] = Field(None, example=-63.1821)
    neighborhood: Optional[str] = Field(None, example="Plan 3000")
    history: Optional[List[ChatMessage]] = Field(default_factory=list)


class EmergencyContact(BaseModel):
    entity: str
    phone: str
    description: str


class AssistantChatResponse(BaseModel):
    reply: str
    safety_level: Literal["SEGURO", "PRECAUCION", "PELIGRO_ALTO", "INFORMATIVO"]
    nearby_incidents_count: int
    active_threats_summary: List[str]
    emergency_contacts: List[EmergencyContact]
    source: str = Field(description="Modelo de IA o motor que generó la respuesta")

