"""
Subscription model for SIMBYP email notifications.
"""
from datetime import datetime
import uuid

from sqlalchemy import Column, String, Boolean, DateTime, ForeignKey, CheckConstraint, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from src.database import Base


class Subscription(Base):
    """
    User subscription to alert types.
    
    Attributes:
        id: Unique identifier (UUID)
        user_id: Foreign key to User
        alert_type: Type of alert ('weekly_alerts' or 'monthly_built_area')
        is_active: Whether subscription is currently active
        subscribed_at: Timestamp when user subscribed
        unsubscribed_at: Timestamp when user unsubscribed (if applicable)
        user: Relationship to User object
    """
    __tablename__ = 'subscriptions'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    alert_type = Column(String(50), nullable=False, index=True)
    is_active = Column(Boolean, default=True, nullable=False, index=True)
    subscribed_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    unsubscribed_at = Column(DateTime, nullable=True)
    
    # Constraints
    __table_args__ = (
        CheckConstraint(
            "alert_type IN ('weekly_alerts', 'monthly_built_area')",
            name='check_alert_type'
        ),
        UniqueConstraint('user_id', 'alert_type', name='unique_user_alert_type'),
    )
    
    # Relationships
    user = relationship('User', back_populates='subscriptions')
    
    def __repr__(self) -> str:
        status = 'active' if self.is_active else 'inactive'
        return f"<Subscription(id={self.id}, user_id={self.user_id}, type='{self.alert_type}', status='{status}')>"
    
    def to_dict(self) -> dict:
        """Convert subscription to dictionary representation."""
        return {
            'id': str(self.id),
            'user_id': str(self.user_id),
            'alert_type': self.alert_type,
            'is_active': self.is_active,
            'subscribed_at': self.subscribed_at.isoformat() if self.subscribed_at else None,
            'unsubscribed_at': self.unsubscribed_at.isoformat() if self.unsubscribed_at else None,
        }
    
    def activate(self) -> None:
        """Activate this subscription."""
        self.is_active = True
        self.unsubscribed_at = None
    
    def deactivate(self) -> None:
        """Deactivate this subscription."""
        self.is_active = False
        self.unsubscribed_at = datetime.utcnow()
    
    @classmethod
    def get_valid_alert_types(cls) -> list[str]:
        """Get list of valid alert types."""
        return ['weekly_alerts', 'monthly_built_area']
