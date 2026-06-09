"""
Subscription repository for CRUD operations on subscriptions.
"""
import logging
from datetime import datetime
from typing import List, Optional
from uuid import UUID

from sqlalchemy import select, func, and_
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from src.models.user import User
from src.models.subscription import Subscription
from src.models.audit import SubscriptionAudit

logger = logging.getLogger(__name__)


class SubscriptionRepository:
    """
    Repository for Subscription entity operations.
    
    Provides CRUD operations with audit logging.
    """
    
    def __init__(self, session: Session):
        """
        Initialize repository with database session.
        
        Args:
            session: SQLAlchemy session
        """
        self.session = session
    
    def subscribe(self, user_id: UUID, alert_type: str, performed_by: str = 'system') -> Subscription:
        """
        Subscribe user to an alert type.
        
        Creates new subscription or reactivates existing one. Logs action to audit.
        
        Args:
            user_id: User UUID
            alert_type: Alert type ('weekly_alerts' or 'monthly_built_area')
            performed_by: Who performed the action (default: 'system')
        
        Returns:
            Subscription object
        
        Raises:
            ValueError: If user not found or invalid alert type
        """
        # Validate user exists
        user = self.session.get(User, user_id)
        if not user:
            raise ValueError(f"User {user_id} not found")
        
        # Validate alert type
        if alert_type not in Subscription.get_valid_alert_types():
            raise ValueError(f"Invalid alert type: {alert_type}")
        
        # Check if subscription already exists
        existing = self.get_subscription(user_id, alert_type)
        
        if existing:
            # Reactivate if inactive
            if not existing.is_active:
                existing.activate()
                self._log_audit(user_id, alert_type, 'reactivated', performed_by)
                logger.info(f"Reactivated subscription: user={user_id}, type={alert_type}")
            else:
                logger.debug(f"Subscription already active: user={user_id}, type={alert_type}")
            return existing
        else:
            # Create new subscription
            subscription = Subscription(
                user_id=user_id,
                alert_type=alert_type,
                is_active=True
            )
            self.session.add(subscription)
            self.session.flush()
            
            # Log audit
            self._log_audit(user_id, alert_type, 'subscribed', performed_by)
            logger.info(f"Created subscription: user={user_id}, type={alert_type}, id={subscription.id}")
            return subscription
    
    def unsubscribe(self, user_id: UUID, alert_type: str, performed_by: str = 'system') -> bool:
        """
        Unsubscribe user from an alert type.
        
        Deactivates subscription and logs action to audit.
        
        Args:
            user_id: User UUID
            alert_type: Alert type
            performed_by: Who performed the action (default: 'system')
        
        Returns:
            True if unsubscribed, False if subscription not found
        """
        subscription = self.get_subscription(user_id, alert_type)
        
        if not subscription:
            logger.warning(f"No subscription found: user={user_id}, type={alert_type}")
            return False
        
        if subscription.is_active:
            subscription.deactivate()
            self._log_audit(user_id, alert_type, 'unsubscribed', performed_by)
            logger.info(f"Unsubscribed: user={user_id}, type={alert_type}")
        else:
            logger.debug(f"Subscription already inactive: user={user_id}, type={alert_type}")
        
        return True
    
    def get_subscription(self, user_id: UUID, alert_type: str) -> Optional[Subscription]:
        """
        Get specific subscription for user and alert type.
        
        Args:
            user_id: User UUID
            alert_type: Alert type
        
        Returns:
            Subscription object or None if not found
        """
        stmt = select(Subscription).where(
            and_(
                Subscription.user_id == user_id,
                Subscription.alert_type == alert_type
            )
        )
        return self.session.execute(stmt).scalar_one_or_none()
    
    def get_user_subscriptions(self, user_id: UUID) -> List[Subscription]:
        """
        Get all subscriptions for a user.
        
        Args:
            user_id: User UUID
        
        Returns:
            List of Subscription objects
        """
        stmt = (
            select(Subscription)
            .where(Subscription.user_id == user_id)
            .order_by(Subscription.alert_type)
        )
        return list(self.session.execute(stmt).scalars().all())
    
    def get_active_subscriptions(self, user_id: UUID) -> List[Subscription]:
        """
        Get active subscriptions for a user.
        
        Args:
            user_id: User UUID
        
        Returns:
            List of active Subscription objects
        """
        stmt = (
            select(Subscription)
            .where(and_(
                Subscription.user_id == user_id,
                Subscription.is_active == True
            ))
            .order_by(Subscription.alert_type)
        )
        return list(self.session.execute(stmt).scalars().all())
    
    def get_recipients_by_alert_type(self, alert_type: str) -> List[str]:
        """
        Get list of recipient emails for an alert type.
        
        Args:
            alert_type: Alert type ('weekly_alerts' or 'monthly_built_area')
        
        Returns:
            List of email addresses
        """
        stmt = (
            select(User.email)
            .join(Subscription)
            .where(and_(
                Subscription.alert_type == alert_type,
                Subscription.is_active == True
            ))
            .order_by(User.email)
        )
        return list(self.session.execute(stmt).scalars().all())
    
    def toggle_subscription(self, subscription_id: UUID, performed_by: str = 'system') -> Optional[Subscription]:
        """
        Toggle subscription active state.
        
        Args:
            subscription_id: Subscription UUID
            performed_by: Who performed the action (default: 'system')
        
        Returns:
            Updated Subscription or None if not found
        """
        subscription = self.session.get(Subscription, subscription_id)
        
        if not subscription:
            return None
        
        if subscription.is_active:
            subscription.deactivate()
            self._log_audit(subscription.user_id, subscription.alert_type, 'unsubscribed', performed_by)
        else:
            subscription.activate()
            self._log_audit(subscription.user_id, subscription.alert_type, 'reactivated', performed_by)
        
        self.session.flush()
        logger.info(f"Toggled subscription {subscription_id}: is_active={subscription.is_active}")
        return subscription
    
    def count_by_alert_type(self, alert_type: str) -> int:
        """
        Count active subscriptions for an alert type.
        
        Args:
            alert_type: Alert type
        
        Returns:
            Count of active subscriptions
        """
        stmt = (
            select(func.count())
            .select_from(Subscription)
            .where(and_(
                Subscription.alert_type == alert_type,
                Subscription.is_active == True
            ))
        )
        return self.session.execute(stmt).scalar()
    
    def _log_audit(self, user_id: UUID, alert_type: str, action: str, performed_by: str, notes: str = None):
        """
        Log subscription action to audit table.
        
        Args:
            user_id: User UUID
            alert_type: Alert type
            action: Action performed
            performed_by: Who performed the action
            notes: Additional notes
        """
        audit = SubscriptionAudit(
            user_id=user_id,
            alert_type=alert_type,
            action=action,
            performed_by=performed_by,
            notes=notes
        )
        self.session.add(audit)
        self.session.flush()
    
    def get_audit_log(self, user_id: UUID, limit: int = 50) -> List[SubscriptionAudit]:
        """
        Get audit log for a user.
        
        Args:
            user_id: User UUID
            limit: Maximum number of entries to return (default: 50)
        
        Returns:
            List of SubscriptionAudit objects
        """
        stmt = (
            select(SubscriptionAudit)
            .where(SubscriptionAudit.user_id == user_id)
            .order_by(SubscriptionAudit.performed_at.desc())
            .limit(limit)
        )
        return list(self.session.execute(stmt).scalars().all())
