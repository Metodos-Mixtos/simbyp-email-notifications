import unittest
from datetime import date
from types import SimpleNamespace
from unittest.mock import Mock
from uuid import uuid4

from src.services.queued_report_sender import send_generated_report_for_type


class TestQueuedReportSender(unittest.TestCase):

    def _build_report(self, alert_type='weekly_alerts'):
        return SimpleNamespace(
            id=uuid4(),
            alert_type=alert_type,
            report_title='Reporte generado',
            report_date=date(2026, 8, 1),
            report_url='gs://reportes-simbyp/reporte_final.html',
            metadata_json={'files': []}
        )

    def test_success_updates_report_status_to_sent(self):
        report = self._build_report('weekly_alerts')
        report_repo = Mock()
        report_repo.get_next_generated_report.return_value = report

        sub_repo = Mock()
        sub_repo.get_recipients_by_alert_type.return_value = ['a@example.com', 'b@example.com']

        payload_builder = Mock(return_value={'id': str(report.id)})
        send_func = Mock(return_value=True)

        response, status_code = send_generated_report_for_type(
            alert_type='weekly_alerts',
            report_label='weekly',
            send_success_message='Weekly report sent successfully',
            report_repo=report_repo,
            sub_repo=sub_repo,
            payload_builder=payload_builder,
            send_func=send_func,
        )

        self.assertEqual(status_code, 200)
        self.assertEqual(response['status'], 'success')
        report_repo.update_report_status.assert_called_once_with(
            report.id,
            status='sent',
            recipient_count=2,
            error_message=None,
        )

    def test_failure_updates_report_status_to_failed(self):
        report = self._build_report('trimestral_alerts')
        report_repo = Mock()
        report_repo.get_next_generated_report.return_value = report

        sub_repo = Mock()
        sub_repo.get_recipients_by_alert_type.return_value = ['a@example.com']

        payload_builder = Mock(return_value={'id': str(report.id)})
        send_func = Mock(return_value=False)

        response, status_code = send_generated_report_for_type(
            alert_type='trimestral_alerts',
            report_label='trimestral',
            send_success_message='Trimestral report sent successfully',
            report_repo=report_repo,
            sub_repo=sub_repo,
            payload_builder=payload_builder,
            send_func=send_func,
        )

        self.assertEqual(status_code, 500)
        self.assertEqual(response['status'], 'error')
        report_repo.update_report_status.assert_called_once()
        args, kwargs = report_repo.update_report_status.call_args
        self.assertEqual(args[0], report.id)
        self.assertEqual(kwargs['status'], 'failed')
        self.assertEqual(kwargs['recipient_count'], 0)
        self.assertIn('trimestral_alerts', kwargs['error_message'])

    def test_skips_when_skip_reason_predicate_matches(self):
        report = self._build_report('weekly_alerts')
        report_repo = Mock()
        report_repo.get_next_generated_report.return_value = report

        sub_repo = Mock()
        payload_builder = Mock(return_value={'metadata': {'alerts_count': 0}})
        send_func = Mock()

        response, status_code = send_generated_report_for_type(
            alert_type='weekly_alerts',
            report_label='weekly',
            send_success_message='Weekly report sent successfully',
            report_repo=report_repo,
            sub_repo=sub_repo,
            payload_builder=payload_builder,
            send_func=send_func,
            skip_reason=lambda payload: (
                'No deforestation alerts detected for this period'
                if (payload.get('metadata') or {}).get('alerts_count') == 0
                else None
            ),
        )

        self.assertEqual(status_code, 200)
        self.assertEqual(response['status'], 'skipped')
        send_func.assert_not_called()
        sub_repo.get_recipients_by_alert_type.assert_not_called()
        report_repo.update_report_status.assert_called_once_with(
            report.id,
            status='skipped',
            recipient_count=0,
            error_message='No deforestation alerts detected for this period',
        )

    def test_skips_when_no_generated_report(self):
        report_repo = Mock()
        report_repo.get_next_generated_report.return_value = None

        sub_repo = Mock()
        payload_builder = Mock()
        send_func = Mock()

        response, status_code = send_generated_report_for_type(
            alert_type='weekly_alerts',
            report_label='weekly',
            send_success_message='Weekly report sent successfully',
            report_repo=report_repo,
            sub_repo=sub_repo,
            payload_builder=payload_builder,
            send_func=send_func,
        )

        self.assertEqual(status_code, 200)
        self.assertEqual(response['status'], 'skipped')
        send_func.assert_not_called()
        report_repo.update_report_status.assert_not_called()


if __name__ == '__main__':
    unittest.main()
