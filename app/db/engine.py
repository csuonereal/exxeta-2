from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.engine.url import make_url
from sqlalchemy.orm import sessionmaker

from app.config import config
from app.db.models import Base


def _ensure_sqlite_parent_dir(database_url: str) -> None:
    if not database_url.startswith("sqlite") or ":memory:" in database_url.lower():
        return
    try:
        u = make_url(database_url)
        if not u.database:
            return
        path = Path(u.database)
        if not path.is_absolute():
            path = Path.cwd() / path
        path.parent.mkdir(parents=True, exist_ok=True)
    except OSError:
        raise


_ensure_sqlite_parent_dir(config.DATABASE_URL)

# Setup SQLite for MVP
engine = create_engine(
    config.DATABASE_URL,
    connect_args={"check_same_thread": False} if config.DATABASE_URL.startswith("sqlite") else {},
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def create_db_and_tables():
    Base.metadata.create_all(bind=engine)

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
