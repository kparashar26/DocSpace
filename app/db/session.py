
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import settings


# Create the database engine
engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,
)


# Create a database session factory
SessionLocal = sessionmaker(
    bind=engine,
    autoflush=False,
    autocommit=False,
)


# Dependency for database sessions
def get_db():
    db = SessionLocal()

    try:
        yield db
    finally:
        db.close()
