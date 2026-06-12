"""
Database configuration.

Defaults to a local SQLite file so the project runs with zero external setup.
To use Supabase / any Postgres, set DATABASE_URL in the environment, e.g.
    DATABASE_URL=postgresql+psycopg://user:pass@host:5432/postgres
"""
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./bharattrust.db")

# check_same_thread is only needed for SQLite + threaded FastAPI
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(DATABASE_URL, connect_args=connect_args, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    """FastAPI dependency that yields a scoped session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
