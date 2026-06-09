"""
Report recipient model for SIMBYP email notifications.
"""
from datetime import datetime
import uuid

from sqlalchemy import Column, String, DateTime, ForeignKey, Text, CheckConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from src.database import Base


class ReportRecipient(Base):
    """
    Individual delivery log for each recipient per report.
    
    Attributes:
        id: Unique identifier (UUID)
        report_id: Foreign key to ReportSent
        user_id: Foreign key to User (NULL if user was deleted)
        email: Email address (denormalized for history)
        delivered_at: Timestamp when delivered
        delivery_status: Delivery status ('queued', 'sent', 'failed', 'bounced')
        error_message: Error details if delivery failed
        report: Relationship to ReportSent object
        user: Relationship to User object
    """
    __tablename__ = 'report_recipients'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    report_id = Column(UUID(as_uuid=True), ForeignKey('reports_sent.id', ondelete='CASCADE'), nullable=False, index=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.id', ondelete='SET NULL'), nullable=True, index=True)
    email = Column(String(255), nullable=False, index=True)
    delivered_at = Column(DateTime, default=datetime.utcnow, index=True)
    delivery_status = Column(String(20), default='sent', index=True)
    error_message = Column(Text, nullable=True)
    
    # Constraints
    __table_args__ = (
        CheckConstraint(
            "delivery_status IN ('queued', 'sent', 'failed', 'bounced')",
            name='check_delivery_status'
        ),
    )
    
    # Relationships
    report = relationship('ReportSent', back_populates='recipients')
    user = relationship('User', back_populates='report_receipts')
    
    def __repr__(self) -> str:
        return f"<ReportRecipient(id={self.id}, email='{self.email}', status='{self.delivery_status}')>"
    
    def to_dict(self) -> dict:
        """Convert recipient to dictionary representation."""
        return {
            'id': str(self.id),
            'report_id': str(self.report_id),
            'user_id': str(self.user_id) if self.user_id else None,
            'email': self.email,
            'delivered_at': self.delivered_at.isoformat() if self.delivered_at else None,
            'delivery_status': self.delivery_status,
            'error_message': self.error_message,
        }
    
    def mark_as_sent(self) -> None:
        """Mark delivery as successful."""
        self.delivery_status = 'sent'
        self.delivered_at = datetime.utcnow()
        self.error_message = None
    
    def mark_as_failed(self, error_message: str) -> None:
        """Mark delivery as failed."""
        self.delivery_status = 'failed'
        self.error_message = error_message
    
    def mark_as_bounced(self, error_message: str = None) -> None:
        """Mark delivery as bounced."""
        self.delivery_status = 'bounced'
        self.error_message = error_message or 'Email bounced'
    
    @classmethod
    def create_for_user(cls, report_id: uuid.UUID, user_id: uuid.UUID, email: str):
        """Factory method to create recipient record for a user."""
        return cls(
            report_id=report_id,
            user_id=user_id,
            email=email.lower().strip(),
            delivery_status='queued'
        )
