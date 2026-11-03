import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.core.database import db_manager
from app.routers.assistant import router as assistant_router
from app.routers.map_zones import router as map_zones_router
from app.routers.reports import router as reports_router

# Configure structured logging
logging.basicConfig(
    level=logging.DEBUG if settings.DEBUG else logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
# Silence verbose pymongo driver heartbeats from debug console
logging.getLogger("pymongo").setLevel(logging.WARNING)
logger = logging.getLogger("rutavecinal")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application Lifespan:
    - On Startup: Initializes MongoDB Motor connection and Beanie ODM documents.
    - On Shutdown: Cleans up connection pools.
    """
    logger.info("Initializing %s...", settings.PROJECT_NAME)
    try:
        await db_manager.connect_and_init()
        logger.info("MongoDB and 2dsphere indexes ready.")
    except Exception as e:
        logger.error("Error connecting to MongoDB: %s. The app will launch with limited capabilities.", str(e))

    yield

    logger.info("Shutting down %s...", settings.PROJECT_NAME)
    await db_manager.close_connection()


app = FastAPI(
    title=settings.PROJECT_NAME,
    description=(
        "API Backend de **Ojo Camba**: Prevención del delito, reporte colaborativo de "
        "accidentes viales y mapeo inteligente de zonas seguras e inseguras con Beanie ODM (MongoDB 2dsphere), "
        "clustering DBSCAN y el agente virtual **Centinela SCZ** impulsado por Google Gemini."
    ),
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register API Routers (direct and /api/v1 compatibility)
app.include_router(reports_router)
app.include_router(map_zones_router)
app.include_router(assistant_router)

app.include_router(reports_router, prefix="/api/v1")
app.include_router(map_zones_router, prefix="/api/v1")
app.include_router(assistant_router, prefix="/api/v1")


@app.get("/", tags=["General"])
async def root():
    """Endpoint de bienvenida e información del servicio."""
    return {
        "system": settings.PROJECT_NAME,
        "version": "1.0.0",
        "city": "Santa Cruz de la Sierra, Bolivia",
        "documentation": "/docs",
        "status": "online",
        "features": [
            "Reportes ciudadanos con triaje IA",
            "Filtro anti-spam con $geoNear",
            "Mapeo de Zonas Rojas/Amarillas/Verdes con DBSCAN",
            "Rutas de patrullaje preventivo",
            "Agente conversacional Centinela SCZ (Gemini 2.5 Flash + Fallback)",
        ],
    }


@app.get("/health", tags=["General"])
async def health_check():
    """Verificación de salud del sistema, base de datos y servicios auxiliares."""
    db_connected = False
    if db_manager.client:
        try:
            await db_manager.client.admin.command("ping")
            db_connected = True
        except Exception:
            db_connected = False

    gemini_configured = bool(settings.GEMINI_API_KEY and settings.GEMINI_API_KEY.strip())

    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={
            "status": "healthy" if db_connected else "degraded",
            "mongodb_connected": db_connected,
            "gemini_api_configured": gemini_configured,
            "gemini_model": settings.GEMINI_MODEL,
            "city_focus": "Santa Cruz de la Sierra (-17.7833, -63.1821)",
        },
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
    )

