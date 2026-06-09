"""
Report repository for tracking sent reports and delivery statistics.
"""
import logging
from datetime import datetime, date, timedelta
from typing import List, Optional, Tuple
from uuid import UUID

from sqlalchemy import select, func, and_, or_, desc, text
from sqlalchemy.orm import Session, joinedload

from src.models.report import ReportSent
from src.models.report_recipient import ReportRecipient
from src.models.alert_statistic import AlertStatistic
from src.models.user import User

logger = logging.getLogger(__name__)


class ReportRepository:
    """
    Repository for report tracking and analytics operations.
    
    Provides methods to log sent reports, track delivery status, and query analytics.
    """
    
    def __init__(self, session: Session):
        """
        Initialize repository with database session.
        
        Args:
            session: SQLAlchemy session
        """
        self.session = session
    
    # ========================================================================
    # Report Logging Methods
    # ========================================================================
    
    def log_report_sent(self, alert_type: str, report_title: str, recipient_emails: List[str],
                       report_url: str = None, report_date: date = None, 
                       metadata: dict = None) -> ReportSent:
        """
        Log a sent email report and its recipients.
        
        Args:
            alert_type: Type of alert ('weekly_alerts' or 'monthly_built_area')
            report_title: Title of the report
            recipient_emails: List of recipient email addresses
            report_url: GCS path or URL to report
            report_date: Date the report covers
            metadata: Additional metadata (alert counts, sources, etc.)
        
        Returns:
            ReportSent object with recipients
        """
        # Create report record
        report = ReportSent(
            alert_type=alert_type,
            report_title=report_title,
            report_url=report_url,
            report_date=report_date or date.today(),
            recipient_count=len(recipient_emails),
            status='sent',
            metadata=metadata
        )
        self.session.add(report)
        self.session.flush()  # Get report ID
        
        # Create recipient records
        for email in recipient_emails:
            # Try to find user by email
            user = self.session.execute(
                select(User).where(User.email == email.lower().strip())
            ).scalar_one_or_none()
            
            recipient = ReportRecipient(
                report_id=report.id,
                user_id=user.id if user else None,
                email=email.lower().strip(),
                delivery_status='sent'
            )
            self.session.add(recipient)
        
        self.session.flush()
        logger.info(f"Logged report: {report_title} to {len(recipient_emails)} recipients")
        return report
    
    def log_report_failure(self, alert_type: str, report_title: str, 
                          error_message: str, metadata: dict = None) -> ReportSent:
        """
        Log a failed report send attempt.
        
        Args:
            alert_type: Type of alert
            report_title: Title of the report
            error_message: Error details
            metadata: Additional metadata
        
        Returns:
            ReportSent object with failed status
        """
        report = ReportSent(
            alert_type=alert_type,
            report_title=report_title,
            status='failed',
            error_message=error_message,
            metadata=metadata
        )
        self.session.add(report)
        self.session.flush()
        logger.warning(f"Logged failed report: {report_title} - {error_message}")
        return report
    
    def update_delivery_status(self, report_id: UUID, email: str, 
                              status: str, error_message: str = None) -> bool:
        """
        Update delivery status for a specific recipient.
        
        Args:
            report_id: Report UUID
            email: Recipient email
            status: New delivery status ('sent', 'failed', 'bounced')
            error_message: Error details if applicable
        
        Returns:
            True if updated, False if recipient not found
        """
        stmt = select(ReportRecipient).where(
            and_(
                ReportRecipient.report_id == report_id,
                ReportRecipient.email == email.lower().strip()
            )
        )
        recipient = self.session.execute(stmt).scalar_one_or_none()
        
        if not recipient:
            return False
        
        recipient.delivery_status = status
        recipient.error_message = error_message
        self.session.flush()
        logger.info(f"Updated delivery status: {email} -> {status}")
        return True
    
    # ========================================================================
    # Report Query Methods
    # ========================================================================
    
    def get_report_by_id(self, report_id: UUID) -> Optional[ReportSent]:
        """
        Get report by ID with recipients.
        
        Args:
            report_id: Report UUID
        
        Returns:
            ReportSent object or None
        """
        stmt = (
            select(ReportSent)
            .options(joinedload(ReportSent.recipients))
            .where(ReportSent.id == report_id)
        )
        return self.session.execute(stmt).scalar_one_or_none()
    
    def list_recent_reports(self, days: int = 30, limit: int = 50) -> List[ReportSent]:
        """
        List recent reports.
        
        Args:
            days: Number of days to look back (default: 30)
            limit: Maximum number of reports (default: 50)
        
        Returns:
            List of ReportSent objects
        """
        since = datetime.utcnow() - timedelta(days=days)
        stmt = (
            select(ReportSent)
            .where(ReportSent.sent_at >= since)
            .order_by(desc(ReportSent.sent_at))
            .limit(limit)
        )
        return list(self.session.execute(stmt).scalars().all())
    
    def list_reports_by_type(self, alert_type: str, days: int = 30) -> List[ReportSent]:
        """
        List reports by alert type.
        
        Args:
            alert_type: Alert type to filter
            days: Number of days to look back
        
        Returns:
            List of ReportSent objects
        """
        since = datetime.utcnow() - timedelta(days=days)
        stmt = (
            select(ReportSent)
            .where(and_(
                ReportSent.alert_type == alert_type,
                ReportSent.sent_at >= since
            ))
            .order_by(desc(ReportSent.sent_at))
        )
        return list(self.session.execute(stmt).scalars().all())
    
    def get_delivery_rate(self, report_id: UUID) -> float:
        """
        Calculate delivery success rate for a report.
        
        Args:
            report_id: Report UUID
        
        Returns:
            Delivery rate as percentage (0-100)
        """
        result = self.session.execute(
            text("SELECT get_report_delivery_rate(:report_id)"),
            {"report_id": report_id}
        ).scalar()
        return float(result) if result else 0.0
    
    # ========================================================================
    # Recipient Query Methods
    # ========================================================================
    
    def get_user_report_history(self, user_id: UUID, limit: int = 50) -> List[ReportRecipient]:
        """
        Get report delivery history for a user.
        
        Args:
            user_id: User UUID
            limit: Maximum number of records
        
        Returns:
            List of ReportRecipient objects
        """
        stmt = (
            select(ReportRecipient)
            .options(joinedload(ReportRecipient.report))
            .where(ReportRecipient.user_id == user_id)
            .order_by(desc(ReportRecipient.delivered_at))
            .limit(limit)
        )
        return list(self.session.execute(stmt).scalars().all())
    
    def get_failed_deliveries(self, days: int = 7) -> List[ReportRecipient]:
        """
        Get failed deliveries in recent days.
        
        Args:
            days: Number of days to look back (default: 7)
        
        Returns:
            List of failed ReportRecipient objects
        """
        since = datetime.utcnow() - timedelta(days=days)
        stmt = (
            select(ReportRecipient)
            .options(joinedload(ReportRecipient.report))
            .where(and_(
                ReportRecipient.delivery_status.in_(['failed', 'bounced']),
                ReportRecipient.delivered_at >= since
            ))
            .order_by(desc(ReportRecipient.delivered_at))
        )
        return list(self.session.execute(stmt).scalars().all())
    
    # ========================================================================
    # Alert Statistics Methods
    # ========================================================================
    
    def log_alert_statistic(self, date: date, alert_type: str, alert_source: str,
                           alert_count: int, municipality_code: str = None,
                           metadata: dict = None) -> AlertStatistic:
        """
        Log or update alert statistics for a date.
        
        Uses INSERT ... ON CONFLICT to update if record already exists.
        
        Args:
            date: Date for statistic
            alert_type: Type of alert
            alert_source: Source ('gfw', 'psa', 'urban_sprawl')
            alert_count: Number of alerts
            municipality_code: Municipality code (optional)
            metadata: Additional metadata
        
        Returns:
            AlertStatistic object
        """
        # Check if stat already exists
        stmt = select(AlertStatistic).where(and_(
            AlertStatistic.date == date,
            AlertStatistic.alert_type == alert_type,
            AlertStatistic.alert_source == alert_source,
            AlertStatistic.municipality_code == municipality_code
        ))
        existing = self.session.execute(stmt).scalar_one_or_none()
        
        if existing:
            # Update existing
            existing.alert_count = alert_count
            existing.metadata = metadata
            self.session.flush()
            logger.info(f"Updated alert stat: {date} {alert_type}/{alert_source} = {alert_count}")
            return existing
        else:
            # Create new
            stat = AlertStatistic(
                date=date,
                alert_type=alert_type,
                alert_source=alert_source,
                alert_count=alert_count,
                municipality_code=municipality_code,
                metadata=metadata
            )
            self.session.add(stat)
            self.session.flush()
            logger.info(f"Created alert stat: {date} {alert_type}/{alert_source} = {alert_count}")
            return stat
    
    def get_alert_trends(self, days: int = 30, alert_type: str = None) -> List[AlertStatistic]:
        """
        Get alert trends for recent days.
        
        Args:
            days: Number of days to look back (default: 30)
            alert_type: Filter by alert type (optional)
        
        Returns:
            List of AlertStatistic objects
        """
        since = date.today() - timedelta(days=days)
        stmt = select(AlertStatistic).where(AlertStatistic.date >= since)
        
        if alert_type:
            stmt = stmt.where(AlertStatistic.alert_type == alert_type)
        
        stmt = stmt.order_by(desc(AlertStatistic.date), AlertStatistic.alert_type)
        return list(self.session.execute(stmt).scalars().all())
    
    def get_total_alerts_by_type(self, start_date: date, end_date: date = None) -> dict:
        """
        Get total alert counts by type for a date range.
        
        Args:
            start_date: Start date
            end_date: End date (default: today)
        
        Returns:
            Dictionary with alert_type as keys and counts as values
        """
        if end_date is None:
            end_date = date.today()
        
        stmt = (
            select(
                AlertStatistic.alert_type,
                func.sum(AlertStatistic.alert_count).label('total')
            )
            .where(and_(
                AlertStatistic.date >= start_date,
                AlertStatistic.date <= end_date
            ))
            .group_by(AlertStatistic.alert_type)
        )
        
        results = self.session.execute(stmt).all()
        return {row.alert_type: row.total for row in results}
    
    # ========================================================================
    # Analytics Methods
    # ========================================================================
    
    def get_reports_summary(self, days: int = 30) -> dict:
        """
        Get summary statistics for reports in recent days.
        
        Args:
            days: Number of days to look back
        
        Returns:
            Dictionary with summary statistics
        """
        since = datetime.utcnow() - timedelta(days=days)
        
        # Total reports by status
        stmt = (
            select(
                ReportSent.status,
                func.count(ReportSent.id).label('count')
            )
            .where(ReportSent.sent_at >= since)
            .group_by(ReportSent.status)
        )
        status_counts = {row.status: row.count for row in self.session.execute(stmt).all()}
        
        # Total recipients
        total_recipients = self.session.execute(
            select(func.sum(ReportSent.recipient_count))
            .where(ReportSent.sent_at >= since)
        ).scalar() or 0
        
        # Delivery statistics
        stmt = (
            select(
                ReportRecipient.delivery_status,
                func.count(ReportRecipient.id).label('count')
            )
            .where(ReportRecipient.delivered_at >= since)
            .group_by(ReportRecipient.delivery_status)
        )
        delivery_counts = {row.delivery_status: row.count for row in self.session.execute(stmt).all()}
        
        return {
            'period_days': days,
            'reports': status_counts,
            'total_recipients': int(total_recipients),
            'deliveries': delivery_counts
        }
    
    def get_user_engagement_score(self, user_id: UUID) -> float:
        """
        Get user engagement score (percentage of reports received).
        
        Args:
            user_id: User UUID
        
        Returns:
            Engagement score as percentage (0-100)
        """
        result = self.session.execute(
            text("SELECT get_user_engagement_score(:user_id)"),
            {"user_id": user_id}
        ).scalar()
        return float(result) if result else 0.0
