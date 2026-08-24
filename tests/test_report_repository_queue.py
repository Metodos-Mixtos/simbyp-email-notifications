import unittest
from unittest.mock import Mock

from src.repositories.report_repository import ReportRepository


class TestReportRepositoryQueueSelection(unittest.TestCase):

    def _setup_repo_with_result(self, result_obj):
        session = Mock()
        execute_result = Mock()
        execute_result.scalar_one_or_none.return_value = result_obj
        session.execute.return_value = execute_result
        return ReportRepository(session), session

    def _extract_compiled_params(self, session):
        stmt = session.execute.call_args.args[0]
        compiled = stmt.compile()
        return compiled.params

    def test_get_next_generated_report_weekly_filters_generated_status(self):
        expected_report = object()
        repo, session = self._setup_repo_with_result(expected_report)

        result = repo.get_next_generated_report('weekly_alerts')

        self.assertIs(result, expected_report)
        params = self._extract_compiled_params(session)
        self.assertEqual(params['alert_type_1'], 'weekly_alerts')
        self.assertEqual(params['status_1'], 'generated')

    def test_get_next_generated_report_trimestral_filters_generated_status(self):
        expected_report = object()
        repo, session = self._setup_repo_with_result(expected_report)

        result = repo.get_next_generated_report('trimestral_alerts')

        self.assertIs(result, expected_report)
        params = self._extract_compiled_params(session)
        self.assertEqual(params['alert_type_1'], 'trimestral_alerts')
        self.assertEqual(params['status_1'], 'generated')


if __name__ == '__main__':
    unittest.main()
