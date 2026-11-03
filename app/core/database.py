import asyncio
import logging
from typing import Optional
from motor.motor_asyncio import AsyncIOMotorClient
from beanie import init_beanie

from app.core.config import settings

logger = logging.getLogger(__name__)


class DatabaseManager:
    """Manages the MongoDB connection pool and Beanie ODM lifecycle."""

    def __init__(self) -> None:
        self.client: Optional[AsyncIOMotorClient] = None

    async def connect_and_init(self) -> None:
        """Establishes connection to MongoDB and registers Beanie documents."""
        # Import models locally to avoid circular dependencies
        from app.models.incident import Incident

        logger.info("Connecting to MongoDB at: %s", settings.MONGODB_URL)
        self.client = AsyncIOMotorClient(settings.MONGODB_URL, serverSelectionTimeoutMS=10000)
        await self.client.admin.command("ping")

        db = self.client[settings.MONGODB_DB_NAME]

        await init_beanie(
            database=db,
            document_models=[
                Incident,
            ],
        )
        logger.info("MongoDB and Beanie ODM initialized successfully for database: %s", settings.MONGODB_DB_NAME)

    async def close_connection(self) -> None:
        """Closes the MongoDB connection pool."""
        if self.client:
            self.client.close()
            logger.info("MongoDB connection closed.")


db_manager = DatabaseManager()

