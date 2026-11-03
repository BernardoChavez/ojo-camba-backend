from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field


class Settings(BaseSettings):
    """Application configuration loaded from environment variables or .env file."""

    PROJECT_NAME: str = "Ojo Camba SCZ Backend"
    ENV: str = "development"
    DEBUG: bool = True
    PORT: int = 8000
    HOST: str = "0.0.0.0"

    # MongoDB Settings
    MONGODB_URL: str = "mongodb://localhost:27017"
    MONGODB_DB_NAME: str = "rutavecinal_scz"

    # Google Gemini API
    GEMINI_API_KEY: str = Field(default="", description="Google Gemini API Key")
    GEMINI_MODEL: str = "gemini-3.5-flash"

    # Anti-Spam / Duplication Thresholds
    SPAM_PROXIMITY_METERS: float = 75.0
    SPAM_WINDOW_MINUTES: int = 30

    # DBSCAN Clustering Parameters
    DBSCAN_EPS_KM: float = 0.4
    DBSCAN_MIN_SAMPLES: int = 3

    # Default Santa Cruz de la Sierra GIS reference center
    DEFAULT_SCZ_LAT: float = -17.7833
    DEFAULT_SCZ_LNG: float = -63.1821

    # CORS
    CORS_ORIGINS: List[str] = ["*"]

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()

