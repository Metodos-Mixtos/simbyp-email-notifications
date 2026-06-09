"""
Alert statistics model for SIMBYP email notifications.
"""
from datetime import datetime, date
import uuid

from sqlalchemy import Column, String, Integer, DateTime, Date, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID, JSONB

from src.database import Base


class AlertStatistic(Base):
    """
    Daily aggregate statistics about alerts.
    
    Attributes:
        id: Unique identifier (UUID)
        date: Date for this statistic
        alert_type: Type of alert
        alert_source: Source of alert data ('gfw', 'psa', 'urban_sprawl')
        alert_count: Number of alerts
        municipality_code: Colombian municipality DIVIPOLA code (optional)
        metadata: Additional metrics in JSON format
        created_at: Timestamp when record was created
    """
    __tablename__ = 'alert_statistics'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    date = Column(Date, nullable=False, index=True)
    alert_type = Column(String(50), nullable=False, index=True)
    alert_source = Column(String(50), nullable=True, index=True)
    alert_count = Column(Integer, default=0)
    municipality_code = Column(String(10), nullable=True, index=True)
    metadata = Column(JSONB, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Unique constraint: one stat per date/type/source/municipality combination
    __table_args__ = (
        UniqueConstraint(
            'date', 'alert_type', 'alert_source', 'municipality_code',
            name='unique_alert_stat',
            postgresql_nulls_not_distinct=False
        ),
    )
    
    def __repr__(self) -> str:
        return f"<AlertStatistic(date={self.date}, type='{self.alert_type}', source='{self.alert_source}', count={self.alert_count})>"
    
    def to_dict(self) -> dict:
        """Convert statistic to dictionary representation."""
        return {
            'id': str(self.id),
            'date': self.date.isoformat(),
            'alert_type': self.alert_type,
            'alert_source': self.alert_source,
            'alert_count': self.alert_count,
            'municipality_code': self.municipality_code,
            'metadata': self.metadata,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }
    
    @classmethod
    def create_gfw_stat(cls, date: date, alert_count: int, municipality_code: str = None, metadata: dict = None):
        """Factory method for GFW (Global Forest Watch) statistics."""
        return cls(
            date=date,
            alert_type='deforestation',
            alert_source='gfw',
            alert_count=alert_count,
            municipality_code=municipality_code,
            metadata=metadata
        )
    
    @classmethod
    def create_psa_stat(cls, date: date, alert_count: int, municipality_code: str = None, metadata: dict = None):
        """Factory method for PSA (land cover) statistics."""
        return cls(
            date=date,
            alert_type='land_cover',
            alert_source='psa',
            alert_count=alert_count,
            municipality_code=municipality_code,
            metadata=metadata
        )
    
    @classmethod
    def create_urban_sprawl_stat(cls, date: date, alert_count: int, municipality_code: str = None, metadata: dict = None):
        """Factory method for urban sprawl/built area statistics."""
        return cls(
            date=date,
            alert_type='built_area',
            alert_source='urban_sprawl',
            alert_count=alert_count,
            municipality_code=municipality_code,
            metadata=metadata
        )
