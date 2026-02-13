import logging
import hashlib
import json
from datetime import datetime, timedelta
from sqlalchemy import create_engine, Column, String, DateTime
from sqlalchemy.orm import sessionmaker, declarative_base
from sqlalchemy.pool import QueuePool
import pytz

logger = logging.getLogger(__name__)

# SQLAlchemy models and engine
Base = declarative_base()

class SentAlert(Base):
    """Track sent alerts to prevent duplicates"""
    __tablename__ = 'sent_alerts'
    
    id = Column(String(255), primary_key=True)
    alert_type = Column(String(50), nullable=False)
    report_name = Column(String(255), nullable=False)
    recipients_hash = Column(String(64), nullable=False)
    recipients_list = Column(String(2000), nullable=False)  # JSON array
    sent_date = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)

# Global engine and session factory
_engine = None
_SessionLocal = None

def init_db_connection():
    """Initialize Cloud SQL connection pool"""
    global _engine, _SessionLocal
    
    if _engine is not None:
        return _SessionLocal
    
    from . import config
    
    if not config.CLOUD_SQL_INSTANCE:
        logger.warning("CLOUD_SQL_INSTANCE not configured; deduplication disabled")
        return None
    
    try:
        from cloud_sql_python_connector import Connector
        
        connector = Connector()
        
        def getconn():
            return connector.connect(
                config.CLOUD_SQL_INSTANCE,
                "pg8000",
                user=config.CLOUD_SQL_USER,
                password=config.CLOUD_SQL_PASSWORD,
                db=config.CLOUD_SQL_DB,
            )
        
        _engine = create_engine(
            "postgresql+pg8000://",
            creator=getconn,
            poolclass=QueuePool,
            pool_size=5,
            max_overflow=10,
        )
        
        # Create tables if they don't exist
        Base.metadata.create_all(_engine)
        
        _SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=_engine)
        logger.info("Cloud SQL connection pool initialized")
        return _SessionLocal
    
    except Exception as e:
        logger.error(f"Failed to initialize Cloud SQL: {e}")
        return None

def get_recipients_hash(recipients: list[str]) -> str:
    """Generate consistent hash of recipients list"""
    sorted_recipients = sorted(set([r.lower().strip() for r in recipients]))
    hash_input = json.dumps(sorted_recipients)
    return hashlib.sha256(hash_input.encode()).hexdigest()

def is_alert_already_sent(alert_type: str, report_name: str, recipients: list[str]) -> bool:
    """Check if alert has already been sent to these recipients"""
    SessionLocal = init_db_connection()
    if SessionLocal is None:
        return False
    
    try:
        recipients_hash = get_recipients_hash(recipients)
        session = SessionLocal()
        
        existing = session.query(SentAlert).filter(
            SentAlert.alert_type == alert_type,
            SentAlert.report_name == report_name,
            SentAlert.recipients_hash == recipients_hash,
        ).first()
        
        session.close()
        return existing is not None
    
    except Exception as e:
        logger.error(f"Error checking sent alerts: {e}")
        return False

def record_sent_alert(alert_type: str, report_name: str, recipients: list[str]) -> bool:
    """Record that alert was sent"""
    SessionLocal = init_db_connection()
    if SessionLocal is None:
        return False
    
    try:
        recipients_hash = get_recipients_hash(recipients)
        recipients_json = json.dumps(sorted(set([r.lower().strip() for r in recipients])))
        
        alert_id = f"{alert_type}_{report_name}_{recipients_hash}_{int(datetime.utcnow().timestamp())}"
        
        sent_alert = SentAlert(
            id=alert_id,
            alert_type=alert_type,
            report_name=report_name,
            recipients_hash=recipients_hash,
            recipients_list=recipients_json,
            sent_date=datetime.utcnow(),
        )
        
        session = SessionLocal()
        session.add(sent_alert)
        session.commit()
        session.close()
        
        logger.info(f"Recorded sent alert: {alert_type}/{report_name} to {len(recipients)} recipients")
        return True
    
    except Exception as e:
        logger.error(f"Error recording sent alert: {e}")
        return False

def is_first_friday_of_month(date: datetime = None) -> bool:
    """Check if given date is the first Friday of its month"""
    if date is None:
        date = datetime.now()
    
    # Friday is weekday 4 (Monday=0)
    if date.weekday() != 4:
        return False
    
    # Check if this Friday is in the first week (1-7)
    return 1 <= date.day <= 7

def get_this_month_first_friday() -> datetime:
    """Get the date of the first Friday of the current month"""
    today = datetime.now()
    year = today.year
    month = today.month
    
    # Start from the first day of the month
    first_day = datetime(year, month, 1)
    
    # Find the first Friday
    days_until_friday = (4 - first_day.weekday()) % 7
    first_friday = first_day + timedelta(days=days_until_friday)
    
    return first_friday


def format_alert_content(alert_type, details):
    if alert_type == "deforestation":
        return f"Alert: Deforestation detected! Details: {details}"
    elif alert_type == "built_area":
        return f"Alert: Built area expansion detected! Details: {details}"
    elif alert_type == "land_cover":
        return f"Alert: Land cover change detected! Details: {details}"
    else:
        return "Unknown alert type."

def validate_email(email):
    import re
    email_regex = r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$'
    return re.match(email_regex, email) is not None

def prepare_email_body(template, context):
    from jinja2 import Environment, FileSystemLoader
    env = Environment(loader=FileSystemLoader('src/templates'))
    template = env.get_template(template)
    return template.render(context)