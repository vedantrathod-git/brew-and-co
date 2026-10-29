from typing import Generator
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.exc import SQLAlchemyError
from app.core.config import settings

# ---------------------------------------------------------------------------
# Connection pool configuration
#
# Defaults are conservative to stay within the limits of small hosted
# PostgreSQL instances (e.g. Neon free tier: 10 simultaneous connections).
#
#   DATABASE_POOL_SIZE     — steady-state connections kept open (default 3)
#   DATABASE_MAX_OVERFLOW  — extra connections allowed under burst load (default 2)
#   DATABASE_POOL_TIMEOUT  — seconds to wait for a pooled connection (default 30)
#   DATABASE_POOL_RECYCLE  — seconds before a connection is recycled (default 1800)
#
# Maximum simultaneous connections = pool_size + max_overflow = 5 by default,
# safely below the Neon free-tier limit of 10.
#
# For a local or dedicated PostgreSQL instance these values can be raised via
# environment variables without any code change.
# ---------------------------------------------------------------------------
engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,      # verify connections before use (handles idle timeouts)
    pool_size=settings.DATABASE_POOL_SIZE,
    max_overflow=settings.DATABASE_MAX_OVERFLOW,
    pool_timeout=settings.DATABASE_POOL_TIMEOUT,
    pool_recycle=settings.DATABASE_POOL_RECYCLE,
    echo=False,
)

# Session factory for creating new database sessions
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
)


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency that provides a database session and ensures proper closure."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def _sanitize_error_message(error: Exception) -> str:
    """Helper to ensure raw passwords or sensitive connection strings never leak in error messages."""
    err_str = str(error)
    # If the configured URL has user:pass, strip out password if it appears in error output
    try:
        if "@" in settings.DATABASE_URL:
            user_part = settings.DATABASE_URL.split("@")[0]
            if ":" in user_part:
                raw_pass = user_part.rsplit(":", 1)[1]
                if raw_pass and raw_pass in err_str:
                    err_str = err_str.replace(raw_pass, "******")
    except Exception:
        pass
    return err_str


def check_db_connection() -> dict:
    """Executes a simple SELECT 1 query using SQLAlchemy to verify connectivity to PostgreSQL.
    
    Returns a dictionary indicating success or safe error details.
    """
    try:
        with engine.connect() as connection:
            result = connection.execute(text("SELECT 1")).scalar()
            return {
                "success": True,
                "status": "connected",
                "database_url": settings.sanitized_database_url,
                "result": result,
            }
    except SQLAlchemyError as err:
        return {
            "success": False,
            "status": "error",
            "database_url": settings.sanitized_database_url,
            "error": _sanitize_error_message(err),
        }
    except Exception as err:
        return {
            "success": False,
            "status": "error",
            "database_url": settings.sanitized_database_url,
            "error": _sanitize_error_message(err),
        }
