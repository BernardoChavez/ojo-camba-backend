from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from beanie import Document
from pydantic import BaseModel, Field, field_validator
import pymongo


class IncidentCategory(str, Enum):
    ROBO = "ROBO"
    ASALTO_MANO_ARMADA = "ASALTO_MANO_ARMADA"
    ACCIDENTE_TRANSITO = "ACCIDENTE_TRANSITO"
    SOSPECHOSO = "SOSPECHOSO"
    LUMINARIA_DEFECTUOSA = "LUMINARIA_DEFECTUOSA"
    CALLE_SIN_ILUMINACION = "CALLE_SIN_ILUMINACION"
    PARQUE_DESCUIDADO = "PARQUE_DESCUIDADO"
    BACHE_VIAL = "BACHE_VIAL"
    MALA_SENALIZACION = "MALA_SENALIZACION"
    ZONA_PANDILLAS = "ZONA_PANDILLAS"
    DISTURBIO_CALLEJERO = "DISTURBIO_CALLEJERO"
    VIOLENCIA_FAMILIAR = "VIOLENCIA_FAMILIAR"
    VENTA_DROGAS = "VENTA_DROGAS"
    OTRO = "OTRO"


class IncidentSeverity(str, Enum):
    LEVE = "LEVE"
    MEDIO = "MEDIO"
    ALTO = "ALTO"
    CRITICO = "CRITICO"


class IncidentStatus(str, Enum):
    ACTIVO = "ACTIVO"
    EN_ATENCION = "EN_ATENCION"
    VERIFICADO = "VERIFICADO"
    RESUELTO = "RESUELTO"
    DESCARTADO = "DESCARTADO"


class GeoJSONPoint(BaseModel):
    """GeoJSON compliant Point geometry: [longitude, latitude]."""

    type: str = "Point"
    coordinates: List[float] = Field(
        ...,
        description="GeoJSON coordinate pair strictly ordered as [longitude, latitude]",
        min_length=2,
        max_length=2,
    )

    @field_validator("coordinates")
    @classmethod
    def validate_coordinates(cls, coords: List[float]) -> List[float]:
        lng, lat = coords[0], coords[1]
        if not (-180.0 <= lng <= 180.0):
            raise ValueError(f"Longitude must be between -180 and 180 degrees. Received: {lng}")
        if not (-90.0 <= lat <= 90.0):
            raise ValueError(f"Latitude must be between -90 and 90 degrees. Received: {lat}")
        return coords


class Incident(Document):
    """Beanie MongoDB Document with 2dsphere spatial index for Santa Cruz incidents."""

    title: str = Field(..., max_length=150)
    description: str = Field(..., max_length=1000)
    category: IncidentCategory
    severity: IncidentSeverity = IncidentSeverity.MEDIO
    status: IncidentStatus = IncidentStatus.ACTIVO

    # Strict GeoJSON Point indexed with 2dsphere
    location: GeoJSONPoint

    neighborhood: Optional[str] = Field(None, max_length=100, description="Barrio o zona de Santa Cruz (ej. Equipetrol, Plan 3000)")
    anillo: Optional[int] = Field(None, ge=1, le=10, description="Número de anillo referencial (1 al 10)")
    reporter_alias: Optional[str] = Field("Vecino Anónimo", max_length=80)
    confirmations_count: int = Field(default=1, ge=1, description="Número de vecinos que corroboraron el hecho")

    # Resumen y triaje generado por el agente IA de Gemini
    ai_triage: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Resultado del triaje automatizado por IA (prioridad, recomendaciones, alerta inmediata)",
    )
    photo_base64: Optional[str] = Field(None, description="Foto de evidencia fotográfica en Base64 o URL")

    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Settings:
        name = "incidents"
        indexes = [
            [("location", pymongo.GEOSPHERE)],
            [("created_at", pymongo.DESCENDING)],
            [("category", pymongo.ASCENDING)],
            [("status", pymongo.ASCENDING)],
            [("neighborhood", pymongo.ASCENDING)],
        ]

    @property
    def longitude(self) -> float:
        return self.location.coordinates[0]

    @property
    def latitude(self) -> float:
        return self.location.coordinates[1]

