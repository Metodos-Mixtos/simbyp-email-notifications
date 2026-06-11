"""
Report model for SIMBYP email notifications.
"""
from datetime import datetime, date
from typing import List, Optional
import uuid

from sqlalchemy import Column, String, Integer, DateTime, Date, Text, CheckConstraint
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import relationship

from src.database import Base


class ReportSent(Base):
    """
    Log of email reports sent by the system.
    
    Attributes:
        id: Unique identifier (UUID)
        alert_type: Type of alert ('weekly_alerts' or 'monthly_built_area')
        report_title: Title of the report
        report_url: GCS path or URL to the report
        report_date: Date the report covers (not when it was sent)
        sent_at: Timestamp when report was sent
        recipient_count: Number of recipients
        status: Overall status ('sent', 'failed', 'partial')
        error_message: Error details if failed
        metadata: Additional metadata (alert counts, sources, etc.)
        recipients: Relationship to ReportRecipient objects
    """
    __tablename__ = 'reports_sent'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    alert_type = Column(String(50), nullable=False, index=True)
    report_title = Column(String(500), nullable=False)
    report_url = Column(Text, nullable=True)
    report_date = Column(Date, nullable=True, index=True)
    sent_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    recipient_count = Column(Integer, default=0)
    status = Column(String(20), default='sent', index=True)
    error_message = Column(Text, nullable=True)
    metadata_json = Column('metadata', JSONB, nullable=True)
    
    # Constraints
    __table_args__ = (
        CheckConstraint(
            "alert_type IN ('weekly_alerts', 'monthly_built_area')",
            name='check_report_alert_type'
        ),
        CheckConstraint(
            "status IN ('generated', 'sent', 'failed', 'partial')",
            name='check_report_status'
        ),
    )
    
    # Relationships
    recipients = relationship(
        'ReportRecipient',
        back_populates='report',
        cascade='all, delete-orphan',
        lazy='select'
    )
    
    def __repr__(self) -> str:
        return f"<ReportSent(id={self.id}, type='{self.alert_type}', title='{self.report_title[:50]}', status='{self.status}')>"
    
    def to_dict(self) -> dict:
        """Convert report to dictionary representation."""
        return {
            'id': str(self.id),
            'alert_type': self.alert_type,
            'report_title': self.report_title,
            'report_url': self.report_url,
            'report_date': self.report_date.isoformat() if self.report_date else None,
            'sent_at': self.sent_at.isoformat() if self.sent_at else None,
            'recipient_count': self.recipient_count,
            'status': self.status,
            'error_message': self.error_message,
            'metadata': self.metadata_json,
        }
    
    def mark_as_sent(self, recipient_count: int) -> None:
        """Mark report as successfully sent."""
        self.status = 'sent'
        self.recipient_count = recipient_count
        self.error_message = None
    
    def mark_as_failed(self, error_message: str) -> None:
        """Mark report as failed."""
        self.status = 'failed'
        self.error_message = error_message
        self.recipient_count = 0
    
    def mark_as_partial(self, successful_count: int, total_count: int, error_message: str = None) -> None:
        """Mark report as partially sent."""
        self.status = 'partial'
        self.recipient_count = total_count
        self.error_message = error_message or f"{successful_count}/{total_count} recipients received the report"
    
    @classmethod
    def create_weekly_report(cls, report_title: str, report_url: str = None, 
                            report_date: date = None, metadata: dict = None):
        """Factory method to create weekly alerts report."""
        return cls(
            alert_type='weekly_alerts',
            report_title=report_title,
            report_url=report_url,
            report_date=report_date or date.today(),
            metadata_json=metadata
        )
    
    @classmethod
    def create_monthly_report(cls, report_title: str, report_url: str = None,
                             report_date: date = None, metadata: dict = None):
        """Factory method to create monthly built area report."""
        return cls(
            alert_type='monthly_built_area',
            report_title=report_title,
            report_url=report_url,
            report_date=report_date or date.today(),
            metadata_json=metadata
        )
