"""
Built Area Monitor Service for tracking and queuing monthly built-area reports.

Handles detection of new urban sprawl / built-area reports produced by
simbyp_area_construida in GCS, parsing metadata, and logging them to the
database as 'generated' reports so /send-monthly-built-area has something to
pick up on the next first Friday of the month.
"""

import json
import logging
from datetime import date
from typing import Optional, Dict, Tuple

from google.cloud import storage
from sqlalchemy import select, and_
from sqlalchemy.orm import Session

from src.models.report import ReportSent
from src.repositories.report_repository import ReportRepository

logger = logging.getLogger(__name__)


class BuiltAreaMonitorService:
    """Service for monitoring and queuing monthly built-area reports from simbyp_area_construida."""

    GCS_BUCKET = "reportes-simbyp"
    GCS_PREFIX = "urban_sprawl"

    def __init__(self, session: Session):
        """
        Initialize built area monitor service.

        Args:
            session: SQLAlchemy database session
        """
        self.session = session
        self.report_repo = ReportRepository(session)

        try:
            self.storage_client = storage.Client()
            self.bucket = self.storage_client.bucket(self.GCS_BUCKET)
        except Exception as e:
            logger.warning(f"GCS initialization failed: {e}. GCS operations will not be available.")
            self.bucket = None

    def check_for_new_report(self, year: int, month: int) -> Tuple[bool, Optional[str]]:
        """
        Check if a built area report exists in GCS for the given year and month.

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
            # Construct blob path: urban_sprawl/2026_08/reportes/urban_sprawl_reporte_2026_08.html
            period = f"{year}_{month:02d}"
            report_name = f"urban_sprawl_reporte_{period}.html"
            blob_path = f"{self.GCS_PREFIX}/{period}/reportes/{report_name}"

            blob = self.bucket.blob(blob_path)
            if blob.exists():
                public_url = f"https://storage.googleapis.com/{self.GCS_BUCKET}/{blob_path}"
                logger.info(f"Found built area report: {public_url}")
                return True, public_url
            else:
                logger.info(f"No built area report found at {blob_path}")
                return False, None

        except Exception as e:
            logger.error(f"Error checking for built area report: {e}")
            return False, None

    def parse_report_metadata(self, year: int, month: int) -> Optional[Dict]:
        """
        Parse metadata (e.g. TOP_UPLS) from the built area report's JSON sidecar.

        Args:
            year: Year (e.g., 2026)
            month: Month (1-12)

        Returns:
            Dictionary with report metadata, or None if not found
        """
        if not self.bucket:
            logger.error("GCS bucket not initialized")
            return None

        try:
            period = f"{year}_{month:02d}"
            blob_path = f"{self.GCS_PREFIX}/{period}/reportes/urban_sprawl_reporte.json"

            blob = self.bucket.blob(blob_path)
            if not blob.exists():
                logger.info(f"No metadata JSON found at {blob_path}")
                return None

            json_content = blob.download_as_text()
            metadata = json.loads(json_content)

            logger.info(f"Parsed metadata for {year}-{month:02d}")
            return metadata

        except Exception as e:
            logger.error(f"Error parsing built area metadata: {e}")
            return None

    def has_queued_report(self, report_url: str) -> bool:
        """
        Check whether this exact report (same GCS url) has already been
        generated/sent, so sync doesn't enqueue duplicates when run more than
        once for the same period.

        Deliberately keyed on report_url rather than report_date/alert_type:
        a report_date collision alone isn't proof this report went out (e.g.
        an unrelated or mislabeled row from before this sync existed could
        share the same month), and that would permanently block the real
        report for that period. The URL is a deterministic, one-to-one
        stand-in for "this specific generated report".

        Args:
            report_url: URL of the report in GCS

        Returns:
            True if a generated/sent report already exists with this URL
        """
        stmt = select(ReportSent).where(and_(
            ReportSent.alert_type == 'monthly_built_area',
            ReportSent.report_url == report_url,
            ReportSent.status.in_(['generated', 'sent']),
        ))
        return self.session.execute(stmt).scalar_one_or_none() is not None

    def log_built_area_report(
        self,
        year: int,
        month: int,
        report_url: str,
        metadata: Optional[Dict] = None
    ) -> Tuple[bool, Optional[str]]:
        """
        Log a built area report to the database with status 'generated'.

        Args:
            year: Year of report
            month: Month of report
            report_url: URL to the report in GCS
            metadata: Optional metadata dictionary (e.g. TOP_UPLS)

        Returns:
            Tuple of (success, report_id)
        """
        try:
            title = f"Reporte Mensual de Área Construida - {self._month_name(month)} {year}"

            report = ReportSent.create_monthly_report(
                report_title=title,
                report_url=report_url,
                report_date=date(year, month, 1),
                metadata=metadata or {},
            )
            self.session.add(report)
            self.session.commit()

            report_id = str(report.id)
            logger.info(f"Logged built area report {report_id} for {year}-{month:02d}")
            return True, report_id

        except Exception as e:
            self.session.rollback()
            logger.error(f"Error logging built area report: {e}")
            return False, None

    def sync_built_area_report(self, year: int, month: int, force: bool = False) -> Tuple[bool, Optional[str]]:
        """
        Complete workflow: check for report, skip if already queued, parse
        metadata, log to DB, return report_id.

        Args:
            year: Year (e.g., 2026)
            month: Month (1-12)
            force: Re-queue even if this exact report_url was already
                generated/sent, for a deliberate manual re-send.

        Returns:
            Tuple of (success, report_id)
        """
        try:
            report_found, report_url = self.check_for_new_report(year, month)
            if not report_found or not report_url:
                logger.info(f"No new built area report for {year}-{month:02d}")
                return False, None

            if not force and self.has_queued_report(report_url):
                logger.info(f"Built area report {report_url} already queued/sent, skipping")
                return False, None

            if force:
                logger.warning(f"Re-queueing built area report {report_url} via manual force=true override")

            metadata = self.parse_report_metadata(year, month)

            return self.log_built_area_report(
                year=year,
                month=month,
                report_url=report_url,
                metadata=metadata
            )

        except Exception as e:
            logger.error(f"Error in sync_built_area_report: {e}")
            return False, None

    def get_latest_report(self) -> Optional[Dict]:
        """
        Get metadata for the latest built area report.

        Returns:
            Dictionary with report details or None
        """
        try:
            report = self.report_repo.get_latest_by_alert_type('monthly_built_area')
            if not report:
                return None

            return {
                'id': str(report.id),
                'title': report.report_title,
                'url': report.report_url,
                'report_date': report.report_date.isoformat() if report.report_date else None,
                'sent_at': report.sent_at.isoformat() if report.sent_at else None,
                'recipient_count': report.recipient_count,
                'status': report.status,
                'metadata': report.metadata_json,
            }

        except Exception as e:
            logger.error(f"Error getting latest built area report: {e}")
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
