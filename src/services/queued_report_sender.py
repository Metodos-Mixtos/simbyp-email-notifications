"""Shared workflow for sending generated report rows from reports_sent."""

import logging
from typing import Callable, Any, Dict, Optional, Tuple

logger = logging.getLogger(__name__)


def send_generated_report_for_type(
    *,
    alert_type: str,
    report_label: str,
    send_success_message: str,
    report_repo,
    sub_repo,
    payload_builder: Callable[[Any], Dict[str, Any]],
    send_func: Callable[[list[str], Dict[str, Any]], bool],
    skip_reason: Optional[Callable[[Dict[str, Any]], Optional[str]]] = None,
) -> Tuple[Dict[str, Any], int]:
    """Send the next generated report for an alert type and persist outcome.

    ``skip_reason`` lets callers opt out of sending a report that was
    generated but has nothing worth emailing (e.g. zero alerts this period).
    If it returns a non-empty string for the built payload, the report is
    marked as skipped instead of sent, so it won't be picked up again.
    """
    report_row = report_repo.get_next_generated_report(alert_type)
    if not report_row:
        logger.info("No generated %s report found to send", report_label)
        return {
            'status': 'skipped',
            'message': f'No generated {report_label} report found',
            'report': None,
        }, 200

    payload = payload_builder(report_row)

    if skip_reason:
        reason = skip_reason(payload)
        if reason:
            logger.info("Skipping %s report %s: %s", report_label, report_row.id, reason)
            report_repo.update_report_status(
                report_row.id,
                status='skipped',
                recipient_count=0,
                error_message=reason,
            )
            return {
                'status': 'skipped',
                'message': reason,
                'report': report_row.report_title,
            }, 200

    recipients = sub_repo.get_recipients_by_alert_type(alert_type)
    if not recipients:
        logger.warning("No recipients configured for %s", alert_type)
        return {
            'status': 'warning',
            'message': 'No recipients configured',
        }, 200

    sent = send_func(recipients, payload)

    if sent:
        report_repo.update_report_status(
            report_row.id,
            status='sent',
            recipient_count=len(recipients),
            error_message=None,
        )
        return {
            'status': 'success',
            'message': send_success_message,
            'report': report_row.report_title,
            'recipients': recipients,
        }, 200

    report_repo.update_report_status(
        report_row.id,
        status='failed',
        recipient_count=0,
        error_message=f'Failed to send {alert_type} report email via Microsoft Graph API',
    )
    return {
        'status': 'error',
        'message': f'Failed to send {report_label} report',
    }, 500