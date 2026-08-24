"""Shared workflow for sending generated report rows from reports_sent."""

import logging
from typing import Callable, Any, Dict, Tuple

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
) -> Tuple[Dict[str, Any], int]:
    """Send the next generated report for an alert type and persist outcome."""
    report_row = report_repo.get_next_generated_report(alert_type)
    if not report_row:
        logger.info("No generated %s report found to send", report_label)
        return {
            'status': 'skipped',
            'message': f'No generated {report_label} report found',
            'report': None,
        }, 200

    recipients = sub_repo.get_recipients_by_alert_type(alert_type)
    if not recipients:
        logger.warning("No recipients configured for %s", alert_type)
        return {
            'status': 'warning',
            'message': 'No recipients configured',
        }, 200

    payload = payload_builder(report_row)
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