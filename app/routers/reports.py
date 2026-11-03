from datetime import datetime
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Query, status

from app.models.incident import Incident, IncidentCategory, IncidentSeverity, IncidentStatus
from app.models.schemas import ConfirmReportResponse, IncidentCreateRequest, IncidentResponse
from app.services.ai_assistant import ai_assistant
from app.services.geo_engine import geo_engine

router = APIRouter(prefix="/reports", tags=["Reportes de Incidentes"])


def serialize_incident(inc: Incident) -> IncidentResponse:
    """Serializes Beanie document to IncidentResponse DTO."""
    return IncidentResponse(
        id=str(inc.id),
        title=inc.title,
        description=inc.description,
        category=inc.category,
        severity=inc.severity,
        status=inc.status,
        location=inc.location,
        latitude=inc.latitude,
        longitude=inc.longitude,
        neighborhood=inc.neighborhood,
        anillo=inc.anillo,
        reporter_alias=inc.reporter_alias,
        confirmations_count=inc.confirmations_count,
        ai_triage=inc.ai_triage,
        created_at=inc.created_at,
        updated_at=inc.updated_at,
    )


@router.post(
    "",
    response_model=IncidentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Registrar un nuevo incidente ciudadano con triaje IA y anti-spam",
)
async def create_report(payload: IncidentCreateRequest):
    """
    Crea un nuevo reporte en el mapa comunitario de Santa Cruz.
    1. Verifica anti-spam ($geoNear): si ya existe un reporte idéntico a menos de 75m
       en los últimos 30 min, incrementa sus confirmaciones sin duplicar.
    2. Ejecuta triaje automatizado con Gemini 2.5 Flash (severidad, sugerencias, entidades).
    3. Indexa con MongoDB 2dsphere en coordenadas estrictas [longitud, latitud].
    """
    # 1. Anti-spam / Duplication filter
    existing_duplicate = await geo_engine.check_duplicate_or_spam(
        longitude=payload.longitude,
        latitude=payload.latitude,
        category=payload.category,
    )

    if existing_duplicate:
        # Increment confirmations and return existing
        existing_duplicate.confirmations_count += 1
        if existing_duplicate.confirmations_count >= 3 and existing_duplicate.status == IncidentStatus.ACTIVO:
            existing_duplicate.status = IncidentStatus.VERIFICADO
        existing_duplicate.updated_at = datetime.utcnow()
        await existing_duplicate.save()
        return serialize_incident(existing_duplicate)

    # 2. AI Triage with resilient fallback
    triage_result = await ai_assistant.triage_report(
        title=payload.title,
        description=payload.description,
        category=payload.category,
        neighborhood=payload.neighborhood,
        anillo=payload.anillo,
    )

    # Determine severity (user provided or AI evaluated)
    if payload.severity:
        severity = payload.severity
    else:
        suggested_str = triage_result.get("suggested_severity", "MEDIO")
        try:
            severity = IncidentSeverity(suggested_str)
        except ValueError:
            severity = IncidentSeverity.MEDIO

    # 3. Create and persist incident
    geojson_location = payload.to_geojson_point()

    new_incident = Incident(
        title=payload.title,
        description=payload.description,
        category=payload.category,
        severity=severity,
        status=IncidentStatus.ACTIVO,
        location=geojson_location,
        neighborhood=payload.neighborhood,
        anillo=payload.anillo,
        reporter_alias=payload.reporter_alias or "Vecino Alerta",
        confirmations_count=1,
        ai_triage=triage_result,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )

    await new_incident.insert()
    return serialize_incident(new_incident)


@router.get(
    "/nearby",
    response_model=List[IncidentResponse],
    summary="Consultar incidentes cercanos por geolocalización (2dsphere)",
)
async def get_nearby_reports(
    latitude: float = Query(..., ge=-90.0, le=90.0, description="Latitud GPS"),
    longitude: float = Query(..., ge=-180.0, le=180.0, description="Longitud GPS"),
    max_distance_meters: float = Query(1000.0, ge=10.0, le=50000.0, description="Radio de búsqueda en metros"),
    category: Optional[IncidentCategory] = Query(None, description="Filtrar por categoría"),
    limit: int = Query(50, ge=1, le=200, description="Cantidad máxima de resultados"),
):
    """
    Retorna incidentes ordenados por proximidad a las coordenadas GPS provistas.
    Utiliza el operador `$near` sobre el índice 2dsphere de MongoDB.
    """
    incidents = await geo_engine.get_nearby_incidents(
        longitude=longitude,
        latitude=latitude,
        max_distance_meters=max_distance_meters,
        category=category,
        limit=limit,
    )
    return [serialize_incident(inc) for inc in incidents]


@router.patch(
    "/{incident_id}/confirm",
    response_model=ConfirmReportResponse,
    summary="Confirmar o corroborar un reporte comunitario",
)
async def confirm_report(incident_id: str):
    """
    Permite a los vecinos corroborar la veracidad de un incidente.
    Al alcanzar 3 o más confirmaciones, el reporte escala a estado VERIFICADO.
    """
    incident = await Incident.get(incident_id)
    if not incident:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No se encontró ningún reporte con ID: {incident_id}",
        )

    incident.confirmations_count += 1
    if incident.confirmations_count >= 3 and incident.status == IncidentStatus.ACTIVO:
        incident.status = IncidentStatus.VERIFICADO

    incident.updated_at = datetime.utcnow()
    await incident.save()

    return ConfirmReportResponse(
        incident_id=str(incident.id),
        confirmations_count=incident.confirmations_count,
        status=incident.status,
        message="Reporte corroborado por la comunidad vecinal.",
    )


@router.get(
    "/{incident_id}",
    response_model=IncidentResponse,
    summary="Obtener detalle de un incidente por ID",
)
async def get_report_by_id(incident_id: str):
    """Obtiene un reporte específico por su ID único de MongoDB."""
    incident = await Incident.get(incident_id)
    if not incident:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Reporte con ID '{incident_id}' no encontrado.",
        )
    return serialize_incident(incident)


@router.get(
    "",
    response_model=List[IncidentResponse],
    summary="Listar últimos incidentes reportados en Santa Cruz",
)
async def list_recent_reports(
    limit: int = Query(50, ge=1, le=200),
    category: Optional[IncidentCategory] = Query(None),
    status_filter: Optional[IncidentStatus] = Query(None, alias="status"),
):
    """Lista los reportes más recientes ordenados cronológicamente descendente."""
    query: dict = {}
    if category:
        query["category"] = category.value
    if status_filter:
        query["status"] = status_filter.value

    incidents = await Incident.find(query).sort("-created_at").limit(limit).to_list()
    return [serialize_incident(inc) for inc in incidents]

