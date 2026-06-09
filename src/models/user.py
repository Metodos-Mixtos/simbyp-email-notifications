"""
User model for SIMBYP email notifications.
"""
from datetime import datetime
from typing import List
import uuid

from sqlalchemy import Column, String, DateTime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from src.database import Base


class User(Base):
    """
    Email recipient user model.
    
    Attributes:
        id: Unique identifier (UUID)
        email: Primary email address (unique)
        name: User's full name
        department: Department or organization
        municipality_code: Colombian municipality DIVIPOLA code
        created_at: Timestamp when user was created
        updated_at: Timestamp when user was last updated
        subscriptions: Relationship to Subscription objects
    """
    __tablename__ = 'users'
    
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=True)
    department = Column(String(255), nullable=True)
    municipality_code = Column(String(10), nullable=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationships
    subscriptions = relationship(
        'Subscription',
        back_populates='user',
        cascade='all, delete-orphan',
        lazy='select'
    )
    
    audit_logs = relationship(
        'SubscriptionAudit',
        back_populates='user',
        cascade='all, delete-orphan',
        lazy='select'
    )
    
    report_receipts = relationship(
        'ReportRecipient',
        back_populates='user',
        lazy='select'
    )
    
    def __repr__(self) -> str:
        return f"<User(id={self.id}, email='{self.email}', name='{self.name}')>"
    
    def to_dict(self) -> dict:
        """Convert user to dictionary representation."""
        return {
            'id': str(self.id),
            'email': self.email,
            'name': self.name,
            'department': self.department,
            'municipality_code': self.municipality_code,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }
    
    def get_active_subscription_types(self) -> List[str]:
        """Get list of active alert types for this user."""
        return [
            sub.alert_type 
            for sub in self.subscriptions 
            if sub.is_active
        ]
    
    def is_subscribed_to(self, alert_type: str) -> bool:
        """Check if user is actively subscribed to an alert type."""
        return any(
            sub.alert_type == alert_type and sub.is_active
            for sub in self.subscriptions
        )
