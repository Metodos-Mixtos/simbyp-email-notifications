"""
Database connection and session management for SIMBYP email notifications.

Provides SQLAlchemy engine, session factory, and connection utilities.
"""
import logging
import os
from contextlib import contextmanager
from typing import Generator

from sqlalchemy import create_engine, event, pool
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from sqlalchemy.engine import Engine

logger = logging.getLogger(__name__)

# SQLAlchemy base for model definitions
Base = declarative_base()

# Global engine and session factory (initialized in init_db)
_engine: Engine | None = None
_SessionFactory: sessionmaker | None = None


def init_db(database_url: str, pool_size: int = 5, max_overflow: int = 10, echo: bool = False) -> None:
    """
    Initialize the database engine and session factory.
    
    Args:
        database_url: PostgreSQL connection string
        pool_size: Number of connections to maintain in the pool (default: 5)
        max_overflow: Maximum connections above pool_size (default: 10)
        echo: Whether to log SQL statements (default: False)
    
    Examples:
        # Cloud Run (Unix socket)
        init_db("postgresql://user:pass@/db?host=/cloudsql/project:region:instance")
        
        # Private IP or Cloud SQL Proxy
        init_db("postgresql://user:pass@10.0.0.1:5432/db")
    """
    global _engine, _SessionFactory
    
    logger.info("Initializing database connection...")
    logger.info(f"Database URL: {_mask_password(database_url)}")
    
    # Create engine with connection pooling
    _engine = create_engine(
        database_url,
        poolclass=pool.QueuePool,
        pool_size=pool_size,
        max_overflow=max_overflow,
        pool_pre_ping=True,  # Verify connections before using
        pool_recycle=3600,   # Recycle connections after 1 hour
        echo=echo,
    )
    
    # Add event listener for connection debugging
    @event.listens_for(_engine, "connect")
    def receive_connect(dbapi_conn, connection_record):
        logger.debug("Database connection established")
    
    # Create session factory
    _SessionFactory = sessionmaker(bind=_engine, expire_on_commit=False)
    
    logger.info("✓ Database initialized successfully")


def get_engine() -> Engine:
    """Get the SQLAlchemy engine instance."""
    if _engine is None:
        raise RuntimeError("Database not initialized. Call init_db() first.")
    return _engine


def get_session_factory() -> sessionmaker:
    """Get the session factory."""
    if _SessionFactory is None:
        raise RuntimeError("Database not initialized. Call init_db() first.")
    return _SessionFactory


@contextmanager
def get_db_session() -> Generator[Session, None, None]:
    """
    Context manager for database sessions with automatic commit/rollback.
    
    Usage:
        with get_db_session() as session:
            user = session.query(User).filter_by(email='test@example.com').first()
            session.commit()
    
    Yields:
        Session: SQLAlchemy session
    
    Raises:
        Exception: Re-raises any exception after rollback
    """
    session_factory = get_session_factory()
    session = session_factory()
    
    try:
        yield session
        session.commit()
    except Exception as e:
        session.rollback()
        logger.error(f"Database session error: {e}", exc_info=True)
        raise
    finally:
        session.close()


def check_db_health() -> tuple[bool, str]:
    """
    Check database connectivity and health.
    
    Returns:
        tuple: (is_healthy: bool, message: str)
    """
    try:
        engine = get_engine()
        
        # Test connection with a simple query
        with engine.connect() as conn:
            result = conn.execute("SELECT 1").scalar()
            if result == 1:
                return True, "Database connection healthy"
            else:
                return False, "Unexpected query result"
                
    except RuntimeError as e:
        return False, f"Database not initialized: {str(e)}"
    except Exception as e:
        logger.error(f"Database health check failed: {e}", exc_info=True)
        return False, f"Database error: {str(e)}"


def close_db() -> None:
    """Close database connections and dispose of the engine."""
    global _engine, _SessionFactory
    
    if _engine:
        logger.info("Closing database connections...")
        _engine.dispose()
        _engine = None
        _SessionFactory = None
        logger.info("✓ Database connections closed")


def _mask_password(url: str) -> str:
    """Mask password in database URL for logging."""
    if '@' not in url:
        return url
    
    try:
        # Split on @ to separate credentials from host
        credentials, rest = url.rsplit('@', 1)
        
        # Split credentials on :// to separate protocol
        if '://' in credentials:
            protocol, creds = credentials.split('://', 1)
            
            # Split credentials on : to separate user and password
            if ':' in creds:
                user, _ = creds.split(':', 1)
                return f"{protocol}://{user}:****@{rest}"
        
        return url
    except Exception:
        return url  # Return original if parsing fails
