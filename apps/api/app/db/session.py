from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from app.core.config import get_settings

settings = get_settings()

engine_options: dict[str, object] = {"future": True}
if settings.database_url.startswith("sqlite"):
    engine_options["connect_args"] = {"check_same_thread": False}

engine = create_engine(settings.database_url, **engine_options)

if settings.database_url.startswith("sqlite"):
    @event.listens_for(engine, "connect")
    def configure_sqlite_connection(dbapi_connection, _connection_record) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys = ON")
        # Keep SQLite's temp/journal writes in memory for local Windows dev setups
        # where on-disk journaling can fail with intermittent disk I/O errors.
        cursor.execute("PRAGMA temp_store = MEMORY")
        cursor.execute("PRAGMA journal_mode = MEMORY")
        cursor.close()

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)
