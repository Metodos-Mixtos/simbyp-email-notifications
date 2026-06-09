"""
Subscription audit model for SIMBYP email notifications.
"""
from datetime import datetime
import uuid

from sqlalchemy import Column, String, DateTime, ForeignKey, Text, CheckConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from src.database import Base


class SubscriptionAudit(Base):
    """
    Audit log for subscription changes.
    
    Attributes:
        id: Unique identifier (UUID)
        user_id: Foreign key to User
        alert_type: Type of alert affected
        action: Action performed ('subscribed', 'unsubscribed', 'reactivated')
        performed_at: Timestamp when action was performed
        performed_by: Email or identifier of who made the change
        notes: Additional notes about the change
        user: Relationship to User object
    """
    __tablename__ = 'subscription_audit'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    alert_type = Column(String(50), nullable=False)
    action = Column(String(20), nullable=False, index=True)
    performed_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    performed_by = Column(String(255), nullable=True)
    notes = Column(Text, nullable=True)
    
    # Constraints
    __table_args__ = (
        CheckConstraint(
            "action IN ('subscribed', 'unsubscribed', 'reactivated')",
            name='check_action_type'
        ),
    )
    
    # Relationships
    user = relationship('User', back_populates='audit_logs')
    
    def __repr__(self) -> str:
        return f"<SubscriptionAudit(id={self.id}, user_id={self.user_id}, action='{self.action}', type='{self.alert_type}')>"
    
    def to_dict(self) -> dict:
        """Convert audit entry to dictionary representation."""
        return {
            'id': str(self.id),
            'user_id': str(self.user_id),
            'alert_type': self.alert_type,
            'action': self.action,
            'performed_at': self.performed_at.isoformat() if self.performed_at else None,
            'performed_by': self.performed_by,
            'notes': self.notes,
        }
    
    @classmethod
    def log_subscription(cls, user_id: uuid.UUID, alert_type: str, performed_by: str = 'system', notes: str = None):
        """Create audit log for subscription action."""
        return cls(
            user_id=user_id,
            alert_type=alert_type,
            action='subscribed',
            performed_by=performed_by,
            notes=notes
        )
    
    @classmethod
    def log_unsubscription(cls, user_id: uuid.UUID, alert_type: str, performed_by: str = 'system', notes: str = None):
        """Create audit log for unsubscription action."""
        return cls(
            user_id=user_id,
            alert_type=alert_type,
            action='unsubscribed',
            performed_by=performed_by,
            notes=notes
        )
    
    @classmethod
    def log_reactivation(cls, user_id: uuid.UUID, alert_type: str, performed_by: str = 'system', notes: str = None):
        """Create audit log for reactivation action."""
        return cls(
            user_id=user_id,
            alert_type=alert_type,
            action='reactivated',
            performed_by=performed_by,
            notes=notes
        )
