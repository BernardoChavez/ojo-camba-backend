# 🇧🇴 OJO CAMBA — Backend GIS & Agente Ciudadano SCZ

Backend de alto rendimiento para **OJO CAMBA**, una plataforma orientada a la **prevención del delito**, **reporte colaborativo de siniestros viales** y **mapeo geoespacial de zonas críticas y corredores seguros** en Santa Cruz de la Sierra, Bolivia.

Construido con **FastAPI**, **MongoDB** (índice espacial `2dsphere` mediante **Motor** y **Beanie ODM**), clustering espacial **DBSCAN** y el agente de inteligencia ciudadana **Centinela SCZ** impulsado por la API de **Google Gemini 2.5 Flash** (`google-genai`).

---

## 🗺️ Características Principales

1. **Indexación Geoespacial Estricta (GeoJSON):**
   - Coordenadas geográficas estrictamente indexadas como `[longitud, latitud]` con índice `2dsphere` sobre MongoDB.
   - Búsquedas por radio con el operador `$near` y canalizaciones de agregación `$geoNear`.
2. **Filtro Anti-Spam Inteligente:**
   - Detecta reportes duplicados de la misma categoría en un radio configurable (default: 75 metros) y ventana de tiempo (default: 30 minutos).
   - En lugar de saturar el mapa, consolida el reporte e incrementa las confirmaciones vecinales.
3. **Mapeo de Zonas Rojas, Amarillas y Verdes (DBSCAN):**
   - Agrupamiento no supervisado mediante `scikit-learn` con métrica `haversine` sobre coordenadas en radianes.
   - Clasificación de cuadrantes:
     - 🔴 **ZONA_ROJA (`#E53935`):** Crítica. Asaltos a mano armada, crímenes violentos o concentración densa.
     - 🟡 **ZONA_AMARILLA (`#FDD835`):** Precaución. Colisiones de micros/taxis, disturbios o sospechosos.
     - 🟢 **ZONA_VERDE (`#43A047`):** Corredores tranquilos, vigilados y bien iluminados.
   - Exportación nativa en formato estándar **GeoJSON `FeatureCollection`**, compatible con Leaflet, Mapbox GL JS, Google Maps y OpenLayers.
4. **Generador de Circuitos de Patrullaje:**
   - Algoritmo que encadena waypoints críticos para optimizar las rondas preventivas de **Radio Patrulla 110** y la **Guardia Municipal**.
5. **Agente Conversacional "Centinela SCZ":**
   - Modelo **Gemini 2.5 Flash** contextualizado con jerga y geografía cruceña (anillos, radiales, boliches, micros, El Cristo, Plan 3000, Equipetrol, Casco Viejo).
   - Inyección en tiempo real de los reportes activos en un radio de 1.2 km alrededor de la posición GPS del usuario.
   - **Resiliencia Total (Fallback Automático):** Si no hay API Key o se corta la conexión con Google GenAI, el sistema activa un motor de contingencia heurístico basado en reglas para no interrumpir el servicio ni el guardado de reportes.

---

## 📂 Arquitectura del Proyecto

```text
rutavecinal-backend/
├── .env.example                 # Plantilla de variables de entorno
├── .env                         # Archivo activo de configuración local
├── requirements.txt             # Dependencias oficiales de producción
├── seed_scz.py                  # Poblador de MongoDB con datos reales de Santa Cruz
├── README.md                    # Documentación completa y guía de uso
└── app/
    ├── __init__.py
    ├── main.py                  # Aplicación FastAPI, Lifespan y CORS
    ├── core/
    │   ├── __init__.py
    │   ├── config.py            # Settings con Pydantic Settings
    │   └── database.py          # Conexión Async Motor + Beanie ODM
    ├── models/
    │   ├── __init__.py
    │   ├── incident.py          # Documento Beanie con 2dsphere y Enums
    │   └── schemas.py           # DTOs de Request / Response (Pydantic v2)
    ├── services/
    │   ├── __init__.py
    │   ├── geo_engine.py        # Haversine, $geoNear anti-spam y DBSCAN
    │   └── ai_assistant.py      # Triaje IA + Centinela SCZ con Gemini 2.5 Flash y fallback
    └── routers/
        ├── __init__.py
        ├── reports.py           # POST /reports, GET /reports/nearby, PATCH /reports/{id}/confirm
        ├── map_zones.py         # GET /map/zones y GET /map/patrol-routes
        └── assistant.py         # POST /assistant/chat
```

---

## 🚀 Instalación y Puesta en Marcha

### 1. Prerrequisitos
- Python 3.10+
- MongoDB 6.0+ en ejecución local o MongoDB Atlas (puerto estándar `27017`)
- (Opcional) Clave de API de Google Gemini en [Google AI Studio](https://aistudio.google.com/)

### 2. Entorno Virtual e Instalación de Dependencias

```bash
cd /home/chavezin/Desktop/rutavecinal-backend

# Crear y activar entorno virtual
python3 -m venv venv
source venv/bin/activate

# Instalar requerimientos
pip install -r requirements.txt
```

### 3. Configurar Variables de Entorno

Edita el archivo `.env`:

```env
PROJECT_NAME="RutaVecinal SCZ Backend"
MONGODB_URL="mongodb://localhost:27017"
MONGODB_DB_NAME="rutavecinal_scz"

# Clave de Gemini (si se deja vacía, el sistema funciona transparentemente con el fallback heurístico)
GEMINI_API_KEY="AIzaSy..."
GEMINI_MODEL="gemini-2.5-flash"

SPAM_PROXIMITY_METERS=75.0
SPAM_WINDOW_MINUTES=30
DBSCAN_EPS_KM=0.4
DBSCAN_MIN_SAMPLES=3
```

### 4. Poblar la Base de Datos con Casos Reales de Santa Cruz

Ejecuta el script de siembra espacial:

```bash
python seed_scz.py
```

Esto insertará reportes con coordenadas exactas de puntos neurálgicos:
- **Plan 3000** (Rotonda El Mechero / Los Chacos)
- **Mercado La Ramada** (Av. Grigotá y 1er/2do Anillo)
- **Mercado Los Pozos** (Suárez Arana / Av. Brasil)
- **El Cristo Redentor** (Monseñor Rivero y 2do Anillo)
- **Equipetrol / Sirari** (Av. San Martín)
- **Villa 1ro de Mayo** (Plaza Principal)
- **Doble Vía a La Guardia** (Km 6)
- **Casco Viejo** (Plaza 24 de Septiembre)
- **Pampa de la Isla** (Virgen de Cotoca y 6to Anillo)

### 5. Iniciar el Servidor de Desarrollo

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Acceso interactivo:
- **Swagger UI:** [http://localhost:8000/docs](http://localhost:8000/docs)
- **ReDoc:** [http://localhost:8000/redoc](http://localhost:8000/redoc)
- **Health Check:** [http://localhost:8000/health](http://localhost:8000/health)

---

## 📡 Endpoints Principales y Ejemplos cURL

### 1. Registrar Reporte Ciudadano (con Triaje IA y Anti-Spam)
`POST /reports`

```bash
curl -X POST "http://localhost:8000/reports" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Asalto armado a transeúnte en la parada",
    "description": "Dos sujetos armados en moto oscura amenazaron a una joven quitándole su celular.",
    "category": "ASALTO_MANO_ARMADA",
    "latitude": -17.8284,
    "longitude": -63.1362,
    "neighborhood": "Plan 3000",
    "anillo": 6,
    "reporter_alias": "Vecino El Mechero"
  }'
```

### 2. Buscar Incidentes Cercanos (2dsphere `$near`)
`GET /reports/nearby`

```bash
curl -X GET "http://localhost:8000/reports/nearby?latitude=-17.8280&longitude=-63.1360&max_distance_meters=1500"
```

### 3. Corroborar Reporte Comunitario
`PATCH /reports/{id}/confirm`

```bash
curl -X PATCH "http://localhost:8000/reports/<ID_DEL_REPORTE>/confirm"
```

### 4. Consultar Zonas Rojas, Amarillas y Verdes (GeoJSON FeatureCollection)
`GET /map/zones`

```bash
curl -X GET "http://localhost:8000/map/zones?eps_km=0.4&min_samples=3"
```

### 5. Obtener Circuito de Patrullaje Óptimo
`GET /map/patrol-routes`

```bash
curl -X GET "http://localhost:8000/map/patrol-routes"
```

### 6. Conversar con Centinela SCZ (Contexto GPS + Gemini 2.5 Flash)
`POST /assistant/chat`

```bash
curl -X POST "http://localhost:8000/assistant/chat" \
  -H "Content-Type: application/json" \
  -d '{
    "message": "¿Es seguro caminar a estas horas por la rotonda del Mechero?",
    "latitude": -17.8284,
    "longitude": -63.1362,
    "neighborhood": "Plan 3000"
  }'
```

---

## 🛡️ Números de Emergencia Integrados (Santa Cruz)

| Entidad | Teléfono | Finalidad |
|---|---|---|
| **Radio Patrulla 110** | `110` / `911` | Emergencias policiales inmediatas y delitos en flagrancia |
| **FELCC Santa Cruz** | `3-3522222` | Investigaciones de robos agravados y homicidios |
| **Tránsito Santa Cruz** | `3-3333333` | Accidentes viales, atropellos y colisiones |
| **FELCV** | `800-140348` | Violencia intrafamiliar y contra la mujer |
| **Bomberos** | `119` / `160` | Incendios y rescate vehicular |
| **Ambulancias SIS** | `168` | Urgencias médicas y traslado hospitalario |
| **Guardia Municipal** | `3-3398888` | Control de espacios públicos y ordenanzas |
