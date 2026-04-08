from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.config import config
from app.db.models import Base

# Setup SQLite for MVP
engine = create_engine(
    config.DATABASE_URL, 
    connect_args={"check_same_thread": False} if config.DATABASE_URL.startswith("sqlite") else {}
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
