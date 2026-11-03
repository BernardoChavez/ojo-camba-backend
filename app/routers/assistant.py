from typing import List
from fastapi import APIRouter

from app.models.incident import Incident
from app.models.schemas import AssistantChatRequest, AssistantChatResponse
from app.services.ai_assistant import ai_assistant
from app.services.geo_engine import geo_engine

router = APIRouter(prefix="/assistant", tags=["Agente IA Centinela SCZ"])


@router.post(
    "/chat",
    response_model=AssistantChatResponse,
    summary="Conversar con el agente Centinela SCZ con contexto GPS y alertas en tiempo real",
)
async def chat_with_assistant(payload: AssistantChatRequest):
    """
    Interacción conversacional con 'Centinela SCZ':
    - Inyecta automáticamente los incidentes activos en un radio de 1200 metros.
    - Utiliza Gemini 2.5 Flash (`google-genai`) para generar respuestas empáticas y preventivas.
    - Si la API no está configurada o la red falla, utiliza el motor de contingencia heurístico sin interrumpir el servicio.
    - Proporciona números de emergencia directos para Santa Cruz de la Sierra (110, FELCC, Bomberos, Ambulancias).
    """
    nearby_incidents: List[Incident] = []

    if payload.latitude is not None and payload.longitude is not None:
        nearby_incidents = await geo_engine.get_nearby_incidents(
            longitude=payload.longitude,
            latitude=payload.latitude,
            max_distance_meters=1200.0,
            limit=10,
        )

    response = await ai_assistant.chat_with_centinela(
        message=payload.message,
        nearby_incidents=nearby_incidents,
        latitude=payload.latitude,
        longitude=payload.longitude,
        neighborhood=payload.neighborhood,
        history=payload.history,
    )

    return response

