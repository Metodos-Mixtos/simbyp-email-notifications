"""
Paramos Monitor Service for tracking and distributing Dynamic World reports.

Handles detection of new paramos reports from Dynamic World service in GCS,
parsing metadata, querying subscribers, and logging reports to the database.
"""

import json
import logging
from datetime import datetime
from typing import Optional, Dict, List, Tuple
from uuid import UUID

from google.cloud import storage
from sqlalchemy.orm import Session

from src.models.report import ReportSent
from src.models.report_recipient import ReportRecipient
from src.repositories.report_repository import ReportRepository
from src.repositories.subscription_repository import SubscriptionRepository

logger = logging.getLogger(__name__)


class ParamosMonitorService:
    """Service for monitoring and managing paramos reports from Dynamic World."""
    
    GCS_BUCKET = "reportes-simbyp"
    GCS_PREFIX = "dynamic_world"
    REPORT_FILENAME_PATTERN = "reporte_paramos_{year}_{month}.html"
    METADATA_FILENAME_PATTERN = "reporte_paramos_{year}_{month}.json"
    
    def __init__(self, session: Session):
        """
        Initialize paramos monitor service.
        
        Args:
            session: SQLAlchemy database session
        """
        self.session = session
        self.report_repo = ReportRepository(session)
        self.subscription_repo = SubscriptionRepository(session)
        
        try:
            self.storage_client = storage.Client()
            self.bucket = self.storage_client.bucket(self.GCS_BUCKET)
        except Exception as e:
            logger.warning(f"GCS initialization failed: {e}. GCS operations will not be available.")
            self.bucket = None
    
    def check_for_new_reports(self, year: int, month: int) -> Tuple[bool, Optional[str]]:
        """
        Check if a new paramos report exists for the given year and month.
        
        Args:
            year: Year (e.g., 2026)
            month: Month (1-12)
            
        Returns:
            Tuple of (report_found, report_url)
        """
        if not self.bucket:
            logger.error("GCS bucket not initialized")
            return False, None
        
        try:
            # Construct blob path: dynamic_world/2026_8/reporte_paramos_2026_8.html
            report_name = f"reporte_paramos_{year}_{month}.html"
            blob_path = f"{self.GCS_PREFIX}/{year}_{month}/{report_name}"
            
            blob = self.bucket.blob(blob_path)
            if blob.exists():
                # Generate public URL
                public_url = f"https://storage.googleapis.com/{self.GCS_BUCKET}/{blob_path}"
                logger.info(f"Found paramos report: {public_url}")
                return True, public_url
            else:
                logger.info(f"No paramos report found at {blob_path}")
                return False, None
                
        except Exception as e:
            logger.error(f"Error checking for paramos report: {e}")
            return False, None
    
    def parse_report_metadata(self, year: int, month: int) -> Optional[Dict]:
        """
        Parse metadata from the paramos report JSON.
        
        Args:
            year: Year (e.g., 2026)
            month: Month (1-12)
            
        Returns:
            Dictionary with report metadata or None if not found
        """
        if not self.bucket:
            logger.error("GCS bucket not initialized")
            return None
        
        try:
            # Construct metadata blob path: dynamic_world/2026_8/reporte_paramos_2026_8.json
            metadata_name = f"reporte_paramos_{year}_{month}.json"
            blob_path = f"{self.GCS_PREFIX}/{year}_{month}/{metadata_name}"
            
            blob = self.bucket.blob(blob_path)
            if not blob.exists():
                logger.warning(f"Metadata not found at {blob_path}")
                return None
            
            # Download and parse JSON
            json_content = blob.download_as_string().decode('utf-8')
            metadata = json.loads(json_content)
            
            logger.info(f"Parsed metadata for {year}-{month}")
            return metadata
            
        except Exception as e:
            logger.error(f"Error parsing paramos metadata: {e}")
            return None
    
    def get_paramos_subscribers(self) -> List[Dict]:
        """
        Get all users subscribed to paramos reports.
        
        Returns:
            List of user dictionaries with id, email, and name
        """
        try:
            subscriptions = self.subscription_repo.get_active_by_alert_type('reporte_paramos')
            
            subscribers = []
            for subscription in subscriptions:
                user = subscription.user
                subscribers.append({
                    'user_id': str(user.id),
                    'email': user.email,
                    'name': user.name,
                })
            
            logger.info(f"Found {len(subscribers)} paramos subscribers")
            return subscribers
            
        except Exception as e:
            logger.error(f"Error getting paramos subscribers: {e}")
            return []
    
    def log_paramos_report(
        self,
        year: int,
        month: int,
        title: str,
        report_url: str,
        recipients: List[Dict],
        metadata: Optional[Dict] = None
    ) -> Tuple[bool, Optional[str]]:
        """
        Log a paramos report to the database with recipient tracking.
        
        Args:
            year: Year of report
            month: Month of report
            title: Report title
            report_url: URL to the report in GCS
            recipients: List of recipient dictionaries (user_id, email, name)
            metadata: Optional metadata dictionary from report
            
        Returns:
            Tuple of (success, report_id)
        """
        try:
            # Prepare report data
            report_data = {
                'alert_type': 'reporte_paramos',
                'report_title': title,
                'report_url': report_url,
                'report_date': None,  # Paramos reports don't have a specific report_date
                'recipient_count': len(recipients),
                'status': 'generated',  # Will be 'sent' after emails are delivered
                'metadata_json': metadata or {},
            }
            
            # Log report_sent
            report_sent = ReportSent(**report_data)
            self.session.add(report_sent)
            self.session.flush()  # Get the ID without committing
            
            report_id = str(report_sent.id)
            
            # Log recipients
            for recipient in recipients:
                recipient_data = {
                    'report_id': report_sent.id,
                    'email': recipient['email'],
                    'user_id': UUID(recipient['user_id']),
                    'status': 'generated',  # Will be 'sent' after email delivery
                }
                report_recipient = ReportRecipient(**recipient_data)
                self.session.add(report_recipient)
            
            self.session.commit()
            logger.info(f"Logged paramos report {report_id} with {len(recipients)} recipients")
            return True, report_id
            
        except Exception as e:
            self.session.rollback()
            logger.error(f"Error logging paramos report: {e}")
            return False, None
    
    def sync_paramos_report(self, year: int, month: int) -> Tuple[bool, Optional[str]]:
        """
        Complete workflow: check for report, parse metadata, log to DB, return report_id.
        
        Args:
            year: Year (e.g., 2026)
            month: Month (1-12)
            
        Returns:
            Tuple of (success, report_id)
        """
        try:
            # Step 1: Check if report exists
            report_found, report_url = self.check_for_new_reports(year, month)
            if not report_found or not report_url:
                logger.info(f"No new paramos report for {year}-{month}")
                return False, None
            
            # Step 2: Parse metadata
            metadata = self.parse_report_metadata(year, month)
            
            # Step 3: Get subscribers
            subscribers = self.get_paramos_subscribers()
            if not subscribers:
                logger.warning("No subscribers for paramos reports")
                return False, None
            
            # Step 4: Log report to database
            title = f"Reporte de Páramos - {self._month_name(month)} {year}"
            success, report_id = self.log_paramos_report(
                year=year,
                month=month,
                title=title,
                report_url=report_url,
                recipients=subscribers,
                metadata=metadata
            )
            
            return success, report_id
            
        except Exception as e:
            logger.error(f"Error in sync_paramos_report: {e}")
            return False, None
    
    def get_latest_report(self) -> Optional[Dict]:
        """
        Get metadata for the latest paramos report.
        
        Returns:
            Dictionary with report details or None
        """
        try:
            report = self.report_repo.get_latest_by_alert_type('reporte_paramos')
            if not report:
                return None
            
            return {
                'id': str(report.id),
                'title': report.report_title,
                'url': report.report_url,
                'sent_at': report.sent_at.isoformat() if report.sent_at else None,
                'recipient_count': report.recipient_count,
                'status': report.status,
                'metadata': report.metadata_json,
            }
            
        except Exception as e:
            logger.error(f"Error getting latest paramos report: {e}")
            return None
    
    @staticmethod
    def _month_name(month: int) -> str:
        """Get Spanish month name."""
        months = {
            1: 'Enero', 2: 'Febrero', 3: 'Marzo',
            4: 'Abril', 5: 'Mayo', 6: 'Junio',
            7: 'Julio', 8: 'Agosto', 9: 'Septiembre',
            10: 'Octubre', 11: 'Noviembre', 12: 'Diciembre'
        }
        return months.get(month, 'Mes desconocido')
