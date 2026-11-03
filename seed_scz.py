"""
seed_scz.py
Script para poblar la base de datos MongoDB con datos geográficos reales
de incidentes, delitos y accidentes viales en Santa Cruz de la Sierra, Bolivia.

Ejecutar:
    python seed_scz.py
"""

import asyncio
from datetime import datetime, timedelta
import random

from motor.motor_asyncio import AsyncIOMotorClient
from beanie import init_beanie

from app.core.config import settings
from app.models.incident import (
    GeoJSONPoint,
    Incident,
    IncidentCategory,
    IncidentSeverity,
    IncidentStatus,
)

SCZ_SEED_DATA = [
    # --- Foco Plan 3000 (Hotspot Peligro / ZONA ROJA) ---
    {
        "title": "Atraco con arma de fuego en rotonda El Mechero",
        "description": "Dos sujetos a bordo de una moto tipo torpedo color azul interceptaron a comerciante y sustrajeron la recaudación del día.",
        "category": IncidentCategory.ASALTO_MANO_ARMADA,
        "severity": IncidentSeverity.CRITICO,
        "status": IncidentStatus.VERIFICADO,
        "lng": -63.1362,
        "lat": -17.8284,
        "neighborhood": "Plan 3000 - El Mechero",
        "anillo": 6,
        "reporter_alias": "Comerciante Mechero",
        "confirmations_count": 7,
    },
    {
        "title": "Robo de celular en parada de micro línea 36",
        "description": "Jóvenes arrancharon el teléfono a una estudiante y escaparon por los callejones oscuros de la curva.",
        "category": IncidentCategory.ROBO,
        "severity": IncidentSeverity.ALTO,
        "status": IncidentStatus.VERIFICADO,
        "lng": -63.1378,
        "lat": -17.8295,
        "neighborhood": "Plan 3000 - Barrio Los Chacos",
        "anillo": 6,
        "reporter_alias": "Vecina Rosa",
        "confirmations_count": 4,
    },
    {
        "title": "Disturbios y gresca callejera entre pandillas",
        "description": "Grupos de jóvenes lanzando piedras y botellas frente al módulo policial. Vecinos temen daños a viviendas.",
        "category": IncidentCategory.DISTURBIO_CALLEJERO,
        "severity": IncidentSeverity.ALTO,
        "status": IncidentStatus.ACTIVO,
        "lng": -63.1350,
        "lat": -17.8270,
        "neighborhood": "Plan 3000",
        "anillo": 6,
        "reporter_alias": "Vecino Don Mario",
        "confirmations_count": 5,
    },
    {
        "title": "Microtráfico en plaza del Mechero",
        "description": "Sujetos sospechosos en banca central comercializando sobres sospechosos en horas de la noche.",
        "category": IncidentCategory.VENTA_DROGAS,
        "severity": IncidentSeverity.ALTO,
        "status": IncidentStatus.ACTIVO,
        "lng": -63.1368,
        "lat": -17.8288,
        "neighborhood": "Plan 3000",
        "anillo": 6,
        "reporter_alias": "Alerta Ciudadana",
        "confirmations_count": 3,
    },

    # --- Foco La Ramada (ZONA ROJA / AMARILLA) ---
    {
        "title": "Robo de carteras y billeteras en pasillo de ropa",
        "description": "Banda de descuideros operando en aglomeración del mercado. Empujan a transeúntes para sustraer pertenencias.",
        "category": IncidentCategory.ROBO,
        "severity": IncidentSeverity.MEDIO,
        "status": IncidentStatus.VERIFICADO,
        "lng": -63.1895,
        "lat": -17.7980,
        "neighborhood": "La Ramada - Av. Grigotá",
        "anillo": 2,
        "reporter_alias": "Comprador Frecuente",
        "confirmations_count": 6,
    },
    {
        "title": "Asalto con cuchillo a pasajero de trufi",
        "description": "Delincuente amenazó con arma punzocortante en parada de trufis interprovinciales.",
        "category": IncidentCategory.ASALTO_MANO_ARMADA,
        "severity": IncidentSeverity.CRITICO,
        "status": IncidentStatus.ACTIVO,
        "lng": -63.1905,
        "lat": -17.7995,
        "neighborhood": "La Ramada Antigua",
        "anillo": 1,
        "reporter_alias": "Conductor Trufi",
        "confirmations_count": 4,
    },
    {
        "title": "Colisión entre micro de la línea 44 y taxi",
        "description": "Giro imprudente a la izquierda causó choque lateral con derrame de aceite en plena avenida Grigotá.",
        "category": IncidentCategory.ACCIDENTE_TRANSITO,
        "severity": IncidentSeverity.MEDIO,
        "status": IncidentStatus.EN_ATENCION,
        "lng": -63.1882,
        "lat": -17.7968,
        "neighborhood": "La Ramada",
        "anillo": 2,
        "reporter_alias": "Testigo Ocular",
        "confirmations_count": 3,
    },

    # --- Foco Los Pozos / Mercado Viejo y Nuevo (ZONA AMARILLA) ---
    {
        "title": "Arranchadores en moto sin placa sobre la Suárez Arana",
        "description": "Motochorro arrebató cartera a señora de la tercera edad y huyó contra ruta hacia el 1er anillo.",
        "category": IncidentCategory.ROBO,
        "severity": IncidentSeverity.ALTO,
        "status": IncidentStatus.VERIFICADO,
        "lng": -63.1755,
        "lat": -17.7788,
        "neighborhood": "Los Pozos - Calle Suárez Arana",
        "anillo": 1,
        "reporter_alias": "Vecino Casco Viejo",
        "confirmations_count": 5,
    },
    {
        "title": "Transeúnte atropellado por vehículo particular",
        "description": "Peatón cruzaba con luz verde en Av. Brasil cuando vagoneta blanca no respetó el semáforo.",
        "category": IncidentCategory.ACCIDENTE_TRANSITO,
        "severity": IncidentSeverity.ALTO,
        "status": IncidentStatus.EN_ATENCION,
        "lng": -63.1742,
        "lat": -17.7802,
        "neighborhood": "Los Pozos - Av. Brasil",
        "anillo": 1,
        "reporter_alias": "Paramédico Voluntario",
        "confirmations_count": 4,
    },

    # --- Foco Rotonda El Cristo y Av. Monseñor Rivero ---
    {
        "title": "Choque múltiple en rotonda del Cristo Redentor",
        "description": "Frenada brusca provocó choque en cadena de tres vehículos. Tráfico totalmente congestionado sobre el 2do anillo.",
        "category": IncidentCategory.ACCIDENTE_TRANSITO,
        "severity": IncidentSeverity.MEDIO,
        "status": IncidentStatus.EN_ATENCION,
        "lng": -63.1815,
        "lat": -17.7708,
        "neighborhood": "El Cristo - 2do Anillo",
        "anillo": 2,
        "reporter_alias": "Conductor Radio Móvil",
        "confirmations_count": 8,
    },
    {
        "title": "Pelea de comensales en salida de local nocturno",
        "description": "Personas en estado de ebriedad protagonizan disturbio con rotura de botellas en acera peatonal.",
        "category": IncidentCategory.DISTURBIO_CALLEJERO,
        "severity": IncidentSeverity.LEVE,
        "status": IncidentStatus.RESUELTO,
        "lng": -63.1805,
        "lat": -17.7725,
        "neighborhood": "Av. Monseñor Rivero",
        "anillo": 1,
        "reporter_alias": "Sereno de Boliche",
        "confirmations_count": 2,
    },

    # --- Foco Equipetrol / Barrio Sirari ---
    {
        "title": "Robo de cerebro electrónico y retrovisores de camioneta",
        "description": "Vehículo estacionado sobre la calle 7 fue violentado mientras los dueños cenaban en restaurante.",
        "category": IncidentCategory.ROBO,
        "severity": IncidentSeverity.MEDIO,
        "status": IncidentStatus.VERIFICADO,
        "lng": -63.1940,
        "lat": -17.7665,
        "neighborhood": "Equipetrol Calle 7",
        "anillo": 3,
        "reporter_alias": "Afectado Equipetrol",
        "confirmations_count": 3,
    },
    {
        "title": "Vehículo sospechoso con vidrios polarizados tomando fotos",
        "description": "Vagoneta ploma sin placa delantera estacionada frente a condominios residenciales por más de dos horas.",
        "category": IncidentCategory.SOSPECHOSO,
        "severity": IncidentSeverity.LEVE,
        "status": IncidentStatus.ACTIVO,
        "lng": -63.1965,
        "lat": -17.7640,
        "neighborhood": "Equipetrol Norte",
        "anillo": 4,
        "reporter_alias": "Seguridad Condominio",
        "confirmations_count": 2,
    },

    # --- Foco Villa 1ro de Mayo ---
    {
        "title": "Asalto armado a farmacia de turno",
        "description": "Sujeto con casco y revolver amenazó a cajera sustrayendo el dinero de caja fuerte.",
        "category": IncidentCategory.ASALTO_MANO_ARMADA,
        "severity": IncidentSeverity.CRITICO,
        "status": IncidentStatus.VERIFICADO,
        "lng": -63.1390,
        "lat": -17.7950,
        "neighborhood": "Villa 1ro de Mayo - Plaza Principal",
        "anillo": 4,
        "reporter_alias": "Bioquímica",
        "confirmations_count": 5,
    },
    {
        "title": "Cables caídos y luminarias apagadas en 3 cuadras",
        "description": "Poste impactado dejó a oscuras todo el manzano, convirtiendo la zona en blanco fácil para asaltantes.",
        "category": IncidentCategory.LUMINARIA_DEFECTUOSA,
        "severity": IncidentSeverity.LEVE,
        "status": IncidentStatus.ACTIVO,
        "lng": -63.1415,
        "lat": -17.7972,
        "neighborhood": "Villa 1ro de Mayo",
        "anillo": 5,
        "reporter_alias": "Junta Vecinal Villa",
        "confirmations_count": 6,
    },

    # --- Foco Doble Vía a La Guardia y 4to/5to Anillo ---
    {
        "title": "Vuelco de camión repartidor de bebidas",
        "description": "Pérdida de frenos en semáforo provocó vuelco lateral. Gran congestión y personas aglomeradas.",
        "category": IncidentCategory.ACCIDENTE_TRANSITO,
        "severity": IncidentSeverity.ALTO,
        "status": IncidentStatus.EN_ATENCION,
        "lng": -63.2200,
        "lat": -17.8240,
        "neighborhood": "Doble Vía a La Guardia Km 6",
        "anillo": 5,
        "reporter_alias": "Vecino Km 6",
        "confirmations_count": 9,
    },

    # --- Foco Santos Dumont y 4to Anillo ---
    {
        "title": "Carrera clandestina de motocicletas y picadas",
        "description": "Grupo numeroso de jóvenes realizando acrobacias peligrosas y ruido ensordecedor sin cascos.",
        "category": IncidentCategory.DISTURBIO_CALLEJERO,
        "severity": IncidentSeverity.MEDIO,
        "status": IncidentStatus.ACTIVO,
        "lng": -63.1860,
        "lat": -17.8220,
        "neighborhood": "Av. Santos Dumont",
        "anillo": 4,
        "reporter_alias": "Vecino Santos Dumont",
        "confirmations_count": 4,
    },

    # --- Foco Casco Viejo / Plaza 24 de Septiembre ---
    {
        "title": "Falso cambista estafando con billetes falsos",
        "description": "Sujeto de contextura gruesa entrega cortes falsos a turistas cerca de la catedral.",
        "category": IncidentCategory.SOSPECHOSO,
        "severity": IncidentSeverity.MEDIO,
        "status": IncidentStatus.VERIFICADO,
        "lng": -63.1821,
        "lat": -17.7833,
        "neighborhood": "Casco Viejo - Plaza Principal",
        "anillo": 1,
        "reporter_alias": "Guía de Turismo",
        "confirmations_count": 3,
    },

    # --- Foco Pampa de la Isla ---
    {
        "title": "Atraco violento en callejón sin luz",
        "description": "Dos sujetos a pie con arma blanca golpearon a vecino para quitarle su motocicleta.",
        "category": IncidentCategory.ASALTO_MANO_ARMADA,
        "severity": IncidentSeverity.CRITICO,
        "status": IncidentStatus.ACTIVO,
        "lng": -63.1200,
        "lat": -17.7750,
        "neighborhood": "Pampa de la Isla",
        "anillo": 6,
        "reporter_alias": "Vecino Pampa",
        "confirmations_count": 4,
    },
]


async def seed_database() -> None:
    """Puebla la base de datos MongoDB con reportes geográficos de Santa Cruz."""
    print("=" * 60)
    print("Iniciando sembrado de datos geoespaciales para RutaVecinal SCZ...")
    print(f"URL MongoDB: {settings.MONGODB_URL}")
    print(f"Base de datos: {settings.MONGODB_DB_NAME}")
    print("=" * 60)

    client = AsyncIOMotorClient(settings.MONGODB_URL)
    db = client[settings.MONGODB_DB_NAME]

    await init_beanie(
        database=db,
        document_models=[Incident],
    )

    # Eliminar datos anteriores para evitar colisiones en pruebas
    deleted_count = await Incident.find_all().delete()
    print(f"Limpieza previa: {deleted_count} incidentes anteriores eliminados.")

    now = datetime.utcnow()
    inserted_docs = []

    for item in SCZ_SEED_DATA:
        # Generar timestamp realista entre hace 48 horas y hace 10 minutos
        minutes_ago = random.randint(10, 48 * 60)
        created_time = now - timedelta(minutes=minutes_ago)

        # Simular resultado de triaje IA pre-computado
        risk_score = 90 if item["severity"] == IncidentSeverity.CRITICO else (
            70 if item["severity"] == IncidentSeverity.ALTO else (
                50 if item["severity"] == IncidentSeverity.MEDIO else 25
            )
        )

        ai_triage = {
            "suggested_severity": item["severity"].value,
            "risk_score": risk_score,
            "immediate_danger": item["severity"] in [IncidentSeverity.CRITICO, IncidentSeverity.ALTO],
            "dispatch_entity": "110 Radio Patrulla" if item["severity"] == IncidentSeverity.CRITICO else "Tránsito / Guardia Municipal",
            "short_summary": f"Reporte de {item['category'].value} en {item['neighborhood']}",
            "preventive_tip": "Transite con precaución y manténgase en contacto con su cuadrante vecinal.",
            "triage_source": "seed_initialization",
        }

        # MongoDB 2dsphere: estricto [longitud, latitud]
        doc = Incident(
            title=item["title"],
            description=item["description"],
            category=item["category"],
            severity=item["severity"],
            status=item["status"],
            location=GeoJSONPoint(type="Point", coordinates=[item["lng"], item["lat"]]),
            neighborhood=item["neighborhood"],
            anillo=item["anillo"],
            reporter_alias=item["reporter_alias"],
            confirmations_count=item["confirmations_count"],
            ai_triage=ai_triage,
            created_at=created_time,
            updated_at=created_time,
        )
        await doc.insert()
        inserted_docs.append(doc)

    print(f"Exito: Se insertaron {len(inserted_docs)} incidentes reales en Santa Cruz de la Sierra.")
    print("Zonas cubiertas:")
    print(" - Plan 3000 (El Mechero)")
    print(" - Mercado La Ramada (Av. Grigotá)")
    print(" - Los Pozos (Suárez Arana / Av. Brasil)")
    print(" - El Cristo Redentor / Monseñor Rivero")
    print(" - Equipetrol / Sirari")
    print(" - Villa 1ro de Mayo")
    print(" - Doble Vía a La Guardia")
    print(" - Casco Viejo / Plaza 24 de Septiembre")
    print(" - Pampa de la Isla")
    print("=" * 60)

    client.close()


if __name__ == "__main__":
    asyncio.run(seed_database())

