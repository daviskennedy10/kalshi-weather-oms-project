import asyncio

from weather_oms.config import Settings
from weather_oms.storage.db import Database
from weather_oms.storage.models import Base


async def create_schema() -> None:
    database = Database(Settings().database_url)
    async with database.engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    await database.close()


if __name__ == "__main__":
    asyncio.run(create_schema())

