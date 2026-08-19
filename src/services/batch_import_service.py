"""
Batch import service for user and subscription management.

Handles CSV file parsing, validation, and upsert operations with 
comprehensive error tracking and audit logging.
"""

import csv
import io
import logging
import re
from typing import Dict, List, Tuple, Optional
from uuid import UUID

from sqlalchemy.orm import Session

from src.models.subscription import Subscription
from src.repositories.user_repository import UserRepository
from src.repositories.subscription_repository import SubscriptionRepository

logger = logging.getLogger(__name__)


class BatchImportError:
    """Represents a single row import error."""
    
    def __init__(self, row_number: int, email: Optional[str] = None, errors: List[str] = None):
        self.row_number = row_number
        self.email = email or "unknown"
        self.errors = errors or []
    
    def to_dict(self) -> Dict:
        return {
            "row": self.row_number,
            "email": self.email,
            "errors": self.errors
        }


class BatchImportResult:
    """Result of a batch import operation."""
    
    def __init__(self):
        self.total_rows = 0
        self.created_count = 0
        self.updated_count = 0
        self.skipped_count = 0
        self.errors: List[BatchImportError] = []
    
    def to_dict(self) -> Dict:
        status = "success" if not self.errors else ("partial" if (self.created_count + self.updated_count) > 0 else "failed")
        return {
            "status": status,
            "summary": {
                "total": self.total_rows,
                "created": self.created_count,
                "updated": self.updated_count,
                "skipped": self.skipped_count,
                "errors": len(self.errors)
            },
            "errors": [e.to_dict() for e in self.errors]
        }


class BatchImportService:
    """
    Service for batch importing users and managing subscriptions from CSV.
    """
    
    # Expected CSV headers
    REQUIRED_HEADERS = {'Correo', 'Nombre'}  # Email and Name are required
    OPTIONAL_HEADERS = {'Departamento', 'Municipio', 'Cargo', 'Entidad'}
    SUBSCRIPTION_HEADERS = {'reporte_gfw', 'monthly_built_area', 'reporte_paramos'}
    
    # Subscription column to alert_type mapping
    SUBSCRIPTION_MAPPING = {
        'reporte_gfw': 'weekly_alerts',
        'monthly_built_area': 'monthly_built_area',
        'reporte_paramos': None,  # Deferred - handled by separate service
    }
    
    def __init__(self, session: Session):
        """
        Initialize batch import service.
        
        Args:
            session: SQLAlchemy database session
        """
        self.session = session
        self.user_repo = UserRepository(session)
        self.subscription_repo = SubscriptionRepository(session)
    
    def import_users_batch(self, csv_file, performed_by: str = 'system') -> BatchImportResult:
        """
        Import users and subscriptions from CSV file.
        
        Args:
            csv_file: File-like object containing CSV data (werkzeug.FileStorage or similar)
            performed_by: User ID or identifier performing the import (for audit logging)
        
        Returns:
            BatchImportResult containing counts and detailed errors
        """
        result = BatchImportResult()
        
        try:
            # Read and decode CSV
            content = csv_file.read()
            if isinstance(content, bytes):
                content = content.decode('utf-8-sig')
            
            # Parse CSV
            csv_reader = csv.DictReader(io.StringIO(content), delimiter=';')
            
            if not csv_reader.fieldnames:
                error = BatchImportError(0, errors=["CSV file is empty or has no headers"])
                result.errors.append(error)
                return result
            
            # Validate headers
            header_validation = self._validate_headers(csv_reader.fieldnames)
            if not header_validation['valid']:
                error = BatchImportError(0, errors=header_validation['errors'])
                result.errors.append(error)
                return result
            
            # Process rows
            for row_num, row in enumerate(csv_reader, start=2):  # Start at 2 because row 1 is headers
                result.total_rows += 1
                
                # Validate and normalize row
                validation_errors, normalized_row = self._validate_and_normalize_row(row, row_num)
                
                if validation_errors:
                    error = BatchImportError(row_num, row.get('Correo', 'unknown'), validation_errors)
                    result.errors.append(error)
                    result.skipped_count += 1
                    continue
                
                # Process the row
                try:
                    is_new = self._process_user_row(normalized_row, performed_by)
                    if is_new:
                        result.created_count += 1
                    else:
                        result.updated_count += 1
                except Exception as e:
                    error_msg = f"Database error: {str(e)}"
                    error = BatchImportError(row_num, normalized_row.get('email'), [error_msg])
                    result.errors.append(error)
                    result.skipped_count += 1
                    logger.error(f"Error processing row {row_num}: {error_msg}")
            
            # Commit successful rows
            try:
                self.session.commit()
                logger.info(f"Batch import completed: {result.created_count} created, {result.updated_count} updated, {len(result.errors)} errors")
            except Exception as e:
                self.session.rollback()
                error = BatchImportError(0, errors=[f"Database commit failed: {str(e)}"])
                result.errors.append(error)
                result.total_rows = 0
                result.created_count = 0
                result.updated_count = 0
                logger.error(f"Failed to commit batch import: {e}")
            
        except Exception as e:
            error = BatchImportError(0, errors=[f"Failed to parse CSV: {str(e)}"])
            result.errors.append(error)
            logger.error(f"CSV parsing error: {e}")
        
        return result
    
    def generate_template_csv(self) -> str:
        """
        Generate a CSV template for batch imports.
        
        Returns:
            CSV content as string
        """
        headers = [
            'Nombre',
            'Cargo',
            'Entidad',
            'reporte_gfw',
            'monthly_built_area',
            'reporte_paramos',
            'Correo',
            'Departamento',
            'Municipio'
        ]
        
        example_rows = [
            [
                'Emilio Rodriguez',
                'Director de Gestión ambiental',
                'Secretaría Distrital de Ambiente',
                '1',
                '0',
                '1',
                'emilio.rodriguez@example.gov.co',
                'Bogotá D.C.',
                '11001'
            ],
            [
                'Maria García',
                'Profesional especializado',
                'Secretaría Distrital de Planeación',
                '0',
                '1',
                '0',
                'maria.garcia@example.gov.co',
                'Bogotá D.C.',
                '11001'
            ]
        ]
        
        output = io.StringIO()
        writer = csv.writer(output, delimiter=';')
        writer.writerow(headers)
        writer.writerows(example_rows)
        
        return output.getvalue()
    
    # Private methods
    
    def _validate_headers(self, headers: List[str]) -> Dict:
        """
        Validate CSV headers.
        
        Args:
            headers: List of header names
        
        Returns:
            Dict with 'valid' bool and 'errors' list
        """
        header_set = set(h.strip() for h in headers if h)
        
        errors = []
        
        # Check required headers
        missing_required = self.REQUIRED_HEADERS - header_set
        if missing_required:
            errors.append(f"Missing required columns: {', '.join(sorted(missing_required))}")
        
        # Check for subscription columns
        has_subscriptions = bool(self.SUBSCRIPTION_HEADERS & header_set)
        if not has_subscriptions:
            errors.append(f"No subscription columns found. Expected at least one of: {', '.join(sorted(self.SUBSCRIPTION_HEADERS))}")
        
        return {
            'valid': len(errors) == 0,
            'errors': errors
        }
    
    def _validate_and_normalize_row(self, row: Dict[str, str], row_number: int) -> Tuple[List[str], Dict]:
        """
        Validate and normalize a single CSV row.
        
        Args:
            row: Dictionary of row data from CSV reader
            row_number: Row number for error reporting
        
        Returns:
            Tuple of (error_list, normalized_row_dict)
        """
        errors = []
        normalized = {}
        
        # Get and validate email
        email = (row.get('Correo') or '').strip()
        if not email:
            errors.append("Email (Correo) is required")
        elif not self._is_valid_email(email):
            errors.append(f"Invalid email format: {email}")
        else:
            normalized['email'] = email.lower()
        
        # Get and validate name
        name = (row.get('Nombre') or '').strip()
        if not name:
            errors.append("Name (Nombre) is required")
        else:
            normalized['name'] = name
        
        # Optional fields - normalize but don't error if missing
        department = (row.get('Departamento') or '').strip()
        if department:
            normalized['department'] = department
        
        municipality = (row.get('Municipio') or '').strip()
        if municipality:
            normalized['municipality_code'] = municipality
        
        # Parse subscriptions
        subscriptions = {}
        for csv_col, alert_type in self.SUBSCRIPTION_MAPPING.items():
            if alert_type is None:  # Skip deferred columns
                continue
            
            value = (row.get(csv_col) or '').strip()
            if value:
                if value not in ('0', '1', 'true', 'false', 'True', 'False'):
                    errors.append(f"Invalid subscription value for {csv_col}: '{value}' (must be 0 or 1)")
                else:
                    # Convert to boolean
                    is_subscribed = value in ('1', 'true', 'True')
                    subscriptions[alert_type] = is_subscribed
        
        normalized['subscriptions'] = subscriptions
        
        return errors, normalized
    
    def _process_user_row(self, normalized_row: Dict, performed_by: str) -> bool:
        """
        Process a single normalized row: create or update user and sync subscriptions.
        
        Args:
            normalized_row: Normalized row data from _validate_and_normalize_row
            performed_by: User ID or identifier performing the import
        
        Returns:
            True if user was created, False if updated
        """
        email = normalized_row['email']
        
        # Check if user exists
        existing_user = self.user_repo.get_by_email(email)
        
        if existing_user:
            # Update existing user
            self.user_repo.update(
                existing_user.id,
                name=normalized_row.get('name'),
                department=normalized_row.get('department'),
                municipality_code=normalized_row.get('municipality_code')
            )
            user_id = existing_user.id
            is_new = False
        else:
            # Create new user
            user = self.user_repo.create(
                email=email,
                name=normalized_row.get('name'),
                department=normalized_row.get('department'),
                municipality_code=normalized_row.get('municipality_code')
            )
            user_id = user.id
            is_new = True
        
        # Sync subscriptions
        subscriptions = normalized_row.get('subscriptions', {})
        if subscriptions:
            self._sync_subscriptions(user_id, subscriptions, performed_by)
        
        return is_new
    
    def _sync_subscriptions(self, user_id: UUID, subscriptions: Dict[str, bool], performed_by: str):
        """
        Sync user subscriptions to match the provided dict.
        
        Args:
            user_id: User UUID
            subscriptions: Dict of {alert_type: is_active}
            performed_by: User ID or identifier performing the action
        """
        current_subscriptions = self.subscription_repo.get_user_subscriptions(user_id)
        current_active = {sub.alert_type: sub.is_active for sub in current_subscriptions}
        
        # Apply changes
        for alert_type, should_be_active in subscriptions.items():
            currently_active = current_active.get(alert_type, False)
            
            if should_be_active and not currently_active:
                # Subscribe
                self.subscription_repo.subscribe(user_id, alert_type, performed_by)
            elif not should_be_active and currently_active:
                # Unsubscribe
                self.subscription_repo.unsubscribe(user_id, alert_type, performed_by)
    
    @staticmethod
    def _is_valid_email(email: str) -> bool:
        """
        Validate email format using a simple regex.
        
        Args:
            email: Email string to validate
        
        Returns:
            True if valid email format
        """
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return bool(re.match(pattern, email))
