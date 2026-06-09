"""
User repository for CRUD operations on users.
"""
import logging
from typing import List, Optional
from uuid import UUID

from sqlalchemy import select, func
from sqlalchemy.orm import Session, joinedload
from sqlalchemy.exc import IntegrityError

from src.models.user import User
from src.models.subscription import Subscription

logger = logging.getLogger(__name__)


class UserRepository:
    """
    Repository for User entity operations.
    
    Provides CRUD operations with proper error handling and transaction management.
    """
    
    def __init__(self, session: Session):
        """
        Initialize repository with database session.
        
        Args:
            session: SQLAlchemy session
        """
        self.session = session
    
    def create(self, email: str, name: str = None, department: str = None, 
               municipality_code: str = None) -> User:
        """
        Create a new user.
        
        Args:
            email: User email (must be unique)
            name: User full name
            department: User department/organization
            municipality_code: Colombian municipality DIVIPOLA code
        
        Returns:
            Created User object
        
        Raises:
            IntegrityError: If email already exists
        """
        try:
            user = User(
                email=email.lower().strip(),
                name=name.strip() if name else None,
                department=department.strip() if department else None,
                municipality_code=municipality_code.strip() if municipality_code else None
            )
            self.session.add(user)
            self.session.flush()  # Get the ID without committing
            logger.info(f"Created user: {user.email} (id={user.id})")
            return user
        except IntegrityError as e:
            self.session.rollback()
            logger.error(f"Failed to create user {email}: {e}")
            raise ValueError(f"User with email {email} already exists") from e
    
    def get_by_id(self, user_id: UUID) -> Optional[User]:
        """
        Get user by ID.
        
        Args:
            user_id: User UUID
        
        Returns:
            User object or None if not found
        """
        return self.session.get(User, user_id)
    
    def get_by_email(self, email: str) -> Optional[User]:
        """
        Get user by email address.
        
        Args:
            email: User email
        
        Returns:
            User object or None if not found
        """
        stmt = select(User).where(User.email == email.lower().strip())
        return self.session.execute(stmt).scalar_one_or_none()
    
    def get_with_subscriptions(self, user_id: UUID) -> Optional[User]:
        """
        Get user with eagerly loaded subscriptions.
        
        Args:
            user_id: User UUID
        
        Returns:
            User object with subscriptions or None if not found
        """
        stmt = (
            select(User)
            .options(joinedload(User.subscriptions))
            .where(User.id == user_id)
        )
        return self.session.execute(stmt).scalar_one_or_none()
    
    def list_all(self, offset: int = 0, limit: int = 100) -> List[User]:
        """
        List all users with pagination.
        
        Args:
            offset: Number of records to skip (default: 0)
            limit: Maximum number of records to return (default: 100)
        
        Returns:
            List of User objects
        """
        stmt = (
            select(User)
            .order_by(User.email)
            .offset(offset)
            .limit(limit)
        )
        return list(self.session.execute(stmt).scalars().all())
    
    def list_by_municipality(self, municipality_code: str, offset: int = 0, limit: int = 100) -> List[User]:
        """
        List users filtered by municipality code.
        
        Args:
            municipality_code: Colombian municipality DIVIPOLA code
            offset: Number of records to skip (default: 0)
            limit: Maximum number of records to return (default: 100)
        
        Returns:
            List of User objects
        """
        stmt = (
            select(User)
            .where(User.municipality_code == municipality_code)
            .order_by(User.email)
            .offset(offset)
            .limit(limit)
        )
        return list(self.session.execute(stmt).scalars().all())
    
    def count(self) -> int:
        """
        Count total number of users.
        
        Returns:
            Total user count
        """
        stmt = select(func.count()).select_from(User)
        return self.session.execute(stmt).scalar()
    
    def update(self, user_id: UUID, **kwargs) -> Optional[User]:
        """
        Update user attributes.
        
        Args:
            user_id: User UUID
            **kwargs: Attributes to update (email, name, department, municipality_code)
        
        Returns:
            Updated User object or None if not found
        
        Raises:
            ValueError: If trying to update to an existing email
        """
        user = self.get_by_id(user_id)
        if not user:
            return None
        
        try:
            # Update allowed fields
            for key in ['name', 'department', 'municipality_code']:
                if key in kwargs:
                    setattr(user, key, kwargs[key])
            
            # Handle email separately (needs lowering and uniqueness check)
            if 'email' in kwargs:
                new_email = kwargs['email'].lower().strip()
                if new_email != user.email:
                    user.email = new_email
            
            self.session.flush()
            logger.info(f"Updated user: {user.email} (id={user.id})")
            return user
        except IntegrityError as e:
            self.session.rollback()
            logger.error(f"Failed to update user {user_id}: {e}")
            raise ValueError(f"Cannot update: email already exists") from e
    
    def delete(self, user_id: UUID) -> bool:
        """
        Delete user (cascades to subscriptions and audit logs).
        
        Args:
            user_id: User UUID
        
        Returns:
            True if deleted, False if user not found
        """
        user = self.get_by_id(user_id)
        if not user:
            return False
        
        email = user.email
        self.session.delete(user)
        self.session.flush()
        logger.info(f"Deleted user: {email} (id={user_id})")
        return True
    
    def exists(self, email: str) -> bool:
        """
        Check if user with email exists.
        
        Args:
            email: User email
        
        Returns:
            True if user exists, False otherwise
        """
        stmt = select(func.count()).select_from(User).where(User.email == email.lower().strip())
        return self.session.execute(stmt).scalar() > 0
