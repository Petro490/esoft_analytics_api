import os
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models import Base

# Загружаем переменные из файла .env
load_dotenv()

def _default_url() -> str:
    """Формирует строку подключения к PostgreSQL из переменных окружения."""
    user = os.getenv("DB_USER", "postgres")
    password = os.getenv("DB_PASSWORD", "")
    host = os.getenv("DB_HOST", "localhost")
    port = os.getenv("DB_PORT", "5432")
    name = os.getenv("DB_NAME", "esoft_analytics_api")
    return f"postgresql://{user}:{password}@{host}:{port}/{name}"


def get_engine(database_url: str | None = None):
    """Создаёт engine. При передаче database_url (например, sqlite для тестов)
    использует его, иначе берёт значения из окружения."""
    url = database_url or _default_url()
    kwargs = {}
    if url.startswith("sqlite"):
        kwargs["connect_args"] = {"check_same_thread": False}
    return create_engine(url, **kwargs)


def create_session_factory(bind):
    """Создаёт SessionLocal, привязанный к переданному engine/bind."""
    return sessionmaker(bind=bind, autocommit=False, autoflush=False)


engine = get_engine()
SessionLocal = create_session_factory(engine)


def init_db(bind=None):
    """Создаёт таблицы, если их нет. bind — обычно engine, опционально для тестов."""
    Base.metadata.create_all(bind=bind or engine)