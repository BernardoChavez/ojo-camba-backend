import json
import logging
from typing import Any, Dict, List, Optional

from app.core.config import settings
from app.models.incident import Incident, IncidentCategory, IncidentSeverity
from app.models.schemas import AssistantChatResponse, ChatMessage, EmergencyContact

logger = logging.getLogger(__name__)

SCZ_EMERGENCY_CONTACTS: List[EmergencyContact] = [
    EmergencyContact(
        entity="Radio Patrulla 110 / Policía Boliviana",
        phone="110",
        description="Atención inmediata de delitos en flagrancia, asaltos y patrullaje de cuadrante.",
    ),
    EmergencyContact(
        entity="FELCC Santa Cruz (Fuerza de Lucha Contra el Crimen)",
        phone="3-3522222",
        description="Denuncias formales de robos agravados, atracos e investigaciones criminales.",
    ),
    EmergencyContact(
        entity="Tránsito Operativo Santa Cruz",
        phone="3-3333333",
        description="Colisiones vehiculares, atropellos y bloqueo de vías en anillos y radiales.",
    ),
    EmergencyContact(
        entity="FELCV (Línea Gratuita Violencia Intrafamiliar)",
        phone="800-140348",
        description="Auxilio y protección ante violencia contra la mujer o el núcleo familiar.",
    ),
    EmergencyContact(
        entity="Bomberos de la Policía / Bomberos Voluntarios",
        phone="119 / 160",
        description="Incendios, rescate vehicular y materiales peligrosos.",
    ),
    EmergencyContact(
        entity="Emergencias Médicas / Ambulancias SIS Santa Cruz",
        phone="168",
        description="Ambulancias y primeros auxilios de urgencia.",
    ),
    EmergencyContact(
        entity="Guardia Municipal Santa Cruz de la Sierra",
        phone="3-3398888",
        description="Control de espacios públicos, mercados, boliches y ruidos molestos.",
    ),
]


class AIAssistantService:
    """
    Intelligent agent service providing:
    1. Automated triage & severity scoring for newly posted incident reports.
    2. 'Centinela SCZ': Conversational AI companion aware of Santa Cruz geography and real-time nearby GPS alerts.
    3. Fully resilient fallback mechanism when Google Gemini API is unavailable or offline.
    """

    def __init__(self) -> None:
        self._client = None
        self._initialized = False

    def _get_genai_client(self):
        """Lazy-load and cache Google GenAI client."""
        if not settings.GEMINI_API_KEY or not settings.GEMINI_API_KEY.strip():
            return None

        if self._client is None and not self._initialized:
            try:
                from google import genai
                self._client = genai.Client(api_key=settings.GEMINI_API_KEY)
                self._initialized = True
                logger.info("Google GenAI client initialized successfully with model: %s", settings.GEMINI_MODEL)
            except Exception as e:
                logger.warning("Could not initialize Google GenAI Client: %s. Using heuristic fallback.", str(e))
                self._client = None
                self._initialized = True
        return self._client

    # =========================================================================
    # 1. INCIDENT REPORT TRIAGE
    # =========================================================================

    async def triage_report(
        self,
        title: str,
        description: str,
        category: IncidentCategory,
        neighborhood: Optional[str] = None,
        anillo: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Evaluates a report with Gemini 2.5 Flash to compute priority, threat level,
        tags, and recommended emergency dispatch.
        Seamlessly falls back to heuristic triage if Gemini is unavailable.
        """
        client = self._get_genai_client()

        if client:
            try:
                prompt = f"""
                Eres el oficial de triaje IA de "Ojo Camba", sistema de seguridad ciudadana de Santa Cruz de la Sierra, Bolivia.
                Analiza el siguiente reporte ciudadano y responde ÚNICAMENTE en formato JSON válido:

                Título: {title}
                Descripción: {description}
                Categoría preliminar: {category.value}
                Barrio: {neighborhood or 'No especificado'}
                Anillo: {anillo or 'No especificado'}

                Estructura JSON requerida:
                {{
                    "suggested_severity": "LEVE" | "MEDIO" | "ALTO" | "CRITICO",
                    "risk_score": 1 a 100,
                    "immediate_danger": true | false,
                    "dispatch_entity": "110 Radio Patrulla" | "Tránsito" | "FELCV" | "Bomberos" | "Guardia Municipal",
                    "short_summary": "resumen en 15 palabras adaptado al léxico cruceño",
                    "preventive_tip": "consejo preventivo para vecinos que transiten la zona",
                    "key_entities": ["vehículo", "arma", "sujetos", etc]
                }}
                """
                response = client.models.generate_content(
                    model=settings.GEMINI_MODEL,
                    contents=prompt,
                )

                raw_text = response.text.strip()
                # Clean codeblock fencing if present
                if raw_text.startswith("```json"):
                    raw_text = raw_text[7:]
                if raw_text.startswith("```"):
                    raw_text = raw_text[3:]
                if raw_text.endswith("```"):
                    raw_text = raw_text[:-3]

                data = json.loads(raw_text.strip())
                data["triage_source"] = settings.GEMINI_MODEL
                return data
            except Exception as e:
                logger.warning("Gemini triage failed (%s), switching to heuristic fallback.", str(e))

        return self._heuristic_triage(title, description, category, neighborhood, anillo)

    def _heuristic_triage(
        self,
        title: str,
        description: str,
        category: IncidentCategory,
        neighborhood: Optional[str],
        anillo: Optional[int],
    ) -> Dict[str, Any]:
        """Rule-based deterministic triage fallback tailored to Santa Cruz context."""
        text = f"{title} {description}".lower()

        is_critical = any(
            w in text for w in ["arma", "disparo", "pistola", "muert", "cuchillo", "apuñal", "rehenes", "fuego"]
        )
        is_high = any(
            w in text for w in ["motochorro", "sangre", "herido", "atropell", "violencia", "golpe", "robo", "asalto"]
        )

        if category == IncidentCategory.ASALTO_MANO_ARMADA or is_critical:
            severity = "CRITICO"
            risk_score = 92
            dispatch = "110 Radio Patrulla - Código Rojo"
            immediate_danger = True
            tip = "Mantenga distancia, no intente confrontar y resguárdese en locales iluminados."
        elif is_high or category in [IncidentCategory.ROBO, IncidentCategory.ACCIDENTE_TRANSITO, IncidentCategory.VIOLENCIA_FAMILIAR, IncidentCategory.ZONA_PANDILLAS]:
            severity = "ALTO"
            risk_score = 80 if category == IncidentCategory.ZONA_PANDILLAS else 75
            dispatch = "110 Radio Patrulla / Módulo Policial EPI" if category == IncidentCategory.ZONA_PANDILLAS else "110 Radio Patrulla / Tránsito SCZ"
            immediate_danger = True
            tip = "Zona con presencia de grupos vandálicos; evite pasar solo y alerte a la junta vecinal." if category == IncidentCategory.ZONA_PANDILLAS else "Evite transitar a pie por la calle afectada y dé aviso a las alarmas vecinales."
        elif category in [IncidentCategory.SOSPECHOSO, IncidentCategory.DISTURBIO_CALLEJERO, IncidentCategory.BACHE_VIAL]:
            severity = "MEDIO"
            risk_score = 55 if category == IncidentCategory.BACHE_VIAL else 50
            dispatch = "Secretaría Municipal de Obras Públicas / Tránsito" if category == IncidentCategory.BACHE_VIAL else "Guardia Municipal / Módulo Policial del Barrio"
            immediate_danger = False
            tip = "Reduzca la velocidad; peligro de daño vehicular, pinchadura o accidente vial." if category == IncidentCategory.BACHE_VIAL else "Circule acompañado y reporte anomalías a su junta vecinal."
        elif category in [IncidentCategory.CALLE_SIN_ILUMINACION, IncidentCategory.LUMINARIA_DEFECTUOSA]:
            severity = "MEDIO"
            risk_score = 45
            dispatch = "Dirección de Alumbrado Público Municipal"
            immediate_danger = False
            tip = "Calle a oscuras; transite preferentemente por la vereda contraria iluminada o acompañado."
        elif category == IncidentCategory.PARQUE_DESCUIDADO:
            severity = "LEVE"
            risk_score = 30
            dispatch = "Dirección de Parques y Jardines / Guardia Municipal"
            immediate_danger = False
            tip = "Área verde con maleza alta o falta de mantenimiento; evite transitar al anochecer."
        elif category == IncidentCategory.MALA_SENALIZACION:
            severity = "LEVE"
            risk_score = 35
            dispatch = "Unidad Operativa de Tránsito / Señalética Urbana SCZ"
            immediate_danger = False
            tip = "Cruce con precaución; intersección sin señalización clara de preferencia de paso."
        else:
            severity = "LEVE"
            risk_score = 25
            dispatch = "Alumbrado Público / Guardia Municipal"
            immediate_danger = False
            tip = "Zona con visibilidad o infraestructura reducida; circule con precaución."

        return {
            "suggested_severity": severity,
            "risk_score": risk_score,
            "immediate_danger": immediate_danger,
            "dispatch_entity": dispatch,
            "short_summary": f"Reporte de {category.value.lower()} en {neighborhood or 'Santa Cruz'}.",
            "preventive_tip": tip,
            "key_entities": [w for w in ["motocicleta", "arma", "micro", "transeunte", "conductor"] if w in text],
            "triage_source": "centinela_heuristic_engine",
        }

    # =========================================================================
    # 2. "CENTINELA SCZ" CONVERSATIONAL AGENT
    # =========================================================================

    async def chat_with_centinela(
        self,
        message: str,
        nearby_incidents: List[Incident],
        latitude: Optional[float] = None,
        longitude: Optional[float] = None,
        neighborhood: Optional[str] = None,
        history: Optional[List[ChatMessage]] = None,
    ) -> AssistantChatResponse:
        """
        Conversational assistant 'Centinela SCZ' that blends real-time GIS incident data,
        local geography (anillos, radiales, barrios), and security advice.
        Falls back to rule-based contextual responses if Gemini is unconfigured or unavailable.
        """
        incidents_summary = []
        has_critical = False
        has_high = False

        for inc in nearby_incidents[:8]:
            inc_info = f"- [{inc.category.value}] {inc.title} en {inc.neighborhood or 'zona circundante'} (Severidad: {inc.severity.value})"
            incidents_summary.append(inc_info)
            if inc.severity == IncidentSeverity.CRITICO or inc.category == IncidentCategory.ASALTO_MANO_ARMADA:
                has_critical = True
            elif inc.severity == IncidentSeverity.ALTO:
                has_high = True

        threats_list = [inc.title for inc in nearby_incidents[:5]]

        if has_critical:
            safety_level = "PELIGRO_ALTO"
        elif has_high or len(nearby_incidents) >= 3:
            safety_level = "PRECAUCION"
        elif len(nearby_incidents) > 0:
            safety_level = "INFORMATIVO"
        else:
            safety_level = "SEGURO"

        client = self._get_genai_client()

        if client:
            try:
                system_instruction = (
                    "Eres 'Centinela SCZ', el agente de inteligencia ciudadana y prevención vial de Santa Cruz de la Sierra, Bolivia. "
                    "Hablas con empatía, profesionalismo, usando términos familiares del contexto cruceño (anillos, radiales, micros, rotondas, barrios como Plan 3000, Equipetrol, Villa 1ro de Mayo, Casco Viejo). "
                    "Tu objetivo primordial es proteger la vida, prevenir asaltos o accidentes y orientar al ciudadano con información verídica y calma."
                )

                gps_context = (
                    f"Coordenadas actuales del usuario: Lat {latitude}, Lng {longitude}. "
                    f"Barrio detectado: {neighborhood or 'Santa Cruz de la Sierra'}.\n"
                    f"Incidentes activos detectados en un radio de 1 km ({len(nearby_incidents)} encontrados):\n"
                    + ("\n".join(incidents_summary) if incidents_summary else "No se registran alertas inmediatas en esta coordenada.")
                )

                user_prompt = f"{gps_context}\n\nPregunta o mensaje del ciudadano:\n{message}"

                response = client.models.generate_content(
                    model=settings.GEMINI_MODEL,
                    contents=f"{system_instruction}\n\n{user_prompt}",
                )

                reply_text = response.text.strip()
                return AssistantChatResponse(
                    reply=reply_text,
                    safety_level=safety_level,
                    nearby_incidents_count=len(nearby_incidents),
                    active_threats_summary=threats_list,
                    emergency_contacts=SCZ_EMERGENCY_CONTACTS,
                    source=settings.GEMINI_MODEL,
                )
            except Exception as e:
                logger.warning("Gemini conversational chat failed (%s), switching to fallback.", str(e))

        # Fallback response generator
        reply_fallback = self._generate_fallback_chat(
            message=message,
            safety_level=safety_level,
            nearby_count=len(nearby_incidents),
            neighborhood=neighborhood,
            incidents_summary=incidents_summary,
        )

        return AssistantChatResponse(
            reply=reply_fallback,
            safety_level=safety_level,
            nearby_incidents_count=len(nearby_incidents),
            active_threats_summary=threats_list,
            emergency_contacts=SCZ_EMERGENCY_CONTACTS,
            source="centinela_fallback_rules",
        )

    def _generate_fallback_chat(
        self,
        message: str,
        safety_level: str,
        nearby_count: int,
        neighborhood: Optional[str],
        incidents_summary: List[str],
    ) -> str:
        """Deterministic safety guidance generator for Santa Cruz citizens."""
        msg_lower = message.lower()
        zone_label = f"la zona de {neighborhood}" if neighborhood else "su ubicación actual en Santa Cruz"

        lines = [
            f"Hola, soy **Centinela SCZ**, tu asistente preventivo de Ojo Camba en {zone_label}."
        ]

        if "emergencia" in msg_lower or "ayuda" in msg_lower or "asalto" in msg_lower:
            lines.append(
                "🚨 **ATENCIÓN INMEDIATA:** Si estás en peligro directo, busca un comercio o punto iluminado y llama de inmediato a **Radio Patrulla 110** o al **911**."
            )

        if nearby_count > 0:
            lines.append(
                f"Hemos detectado **{nearby_count} reporte(s)** activos en tu cuadrante cercano:"
            )
            for item in incidents_summary[:4]:
                lines.append(item)
            lines.append(
                "💡 **Recomendación:** Evita el uso expuesto del teléfono celular sobre la vía pública y mantente atento a motocicletas sospechosas sin placa."
            )
        else:
            lines.append(
                "✅ Tu sector no presenta reportes delictivos ni siniestros viales recientes registrados en la base comunitaria. Puedes transitar con normalidad manteniendo precauciones básicas."
            )

        if "ruta" in msg_lower or "ir" in msg_lower or "camino" in msg_lower:
            lines.append(
                "🚗 **Consejo vial cruceño:** Para desplazamientos nocturnos, prioriza avenidas principales iluminadas (anillos principales, Av. Cristo Redentor, Av. San Martín o Doble Vía a La Guardia) en lugar de calles secundarias oscuras."
            )

        return "\n\n".join(lines)


ai_assistant = AIAssistantService()

