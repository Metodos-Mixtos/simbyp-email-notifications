import unittest
from unittest.mock import patch, MagicMock, Mock
from datetime import datetime
from src.email_service import EmailService

class TestEmailService(unittest.TestCase):

    def setUp(self):
        """Set up test fixtures with required Azure AD credentials"""
        self.email_service = EmailService(
            client_id='test-client-id',
            tenant_id='test-tenant-id',
            client_secret='test-client-secret',
            from_email='test@example.com',
            from_name='Test Sender'
        )

    @patch('src.email_service.requests.post')
    @patch.object(EmailService, '_get_access_token')
    def test_send_weekly_alerts(self, mock_get_token, mock_post):
        """Test sending weekly alerts email via Microsoft Graph API"""
        # Mock Azure AD token
        mock_get_token.return_value = 'fake-access-token'
        
        # Mock successful Graph API response
        mock_response = Mock()
        mock_response.status_code = 202
        mock_response.text = ''
        mock_post.return_value = mock_response
        
        alerts = {
            'deforestation': [
                {
                    'type': 'gfw_deforestation',
                    'title': 'Test GFW Alert',
                    'updated': datetime.now(),
                    'url': 'https://example.com/report.html',
                    'report_name': 'report.html'
                }
            ],
            'land_cover': []
        }
        recipients = ['test@example.com']
        
        result = self.email_service.send_weekly_alerts(recipients, alerts)
        self.assertTrue(result)
        mock_post.assert_called_once()
        mock_get_token.assert_called_once()

    @patch('src.email_service.requests.post')
    @patch.object(EmailService, '_get_access_token')
    def test_send_weekly_alerts_no_data(self, mock_get_token, mock_post):
        """Test weekly alerts with no data (no API call should be made)"""
        alerts = {
            'deforestation': [],
            'land_cover': []
        }
        recipients = ['test@example.com']
        
        result = self.email_service.send_weekly_alerts(recipients, alerts)
        self.assertFalse(result)
        # Should not call Graph API when there's no data
        mock_post.assert_not_called()
        mock_get_token.assert_not_called()

    @patch('src.email_service.requests.post')
    @patch.object(EmailService, '_get_access_token')
    def test_send_monthly_built_area(self, mock_get_token, mock_post):
        """Test sending monthly built area email via Microsoft Graph API"""
        # Mock Azure AD token
        mock_get_token.return_value = 'fake-access-token'
        
        # Mock successful Graph API response
        mock_response = Mock()
        mock_response.status_code = 202
        mock_response.text = ''
        mock_post.return_value = mock_response
        
        alert_data = {
            'alerts': [
                {
                    'type': 'area_construida',
                    'title': 'Built Area Alert',
                    'updated': datetime.now(),
                    'url': 'https://example.com/report.html',
                    'report_name': 'report.html'
                }
            ],
            'count': 1,
            'title': 'Reporte Mensual'
        }
        recipients = ['test@example.com']
        
        result = self.email_service.send_monthly_built_area(recipients, alert_data)
        self.assertTrue(result)
        mock_post.assert_called_once()
        mock_get_token.assert_called_once()

    @patch('src.email_service.requests.post')
    @patch.object(EmailService, '_get_access_token')
    def test_send_monthly_built_area_no_data(self, mock_get_token, mock_post):
        """Test monthly built area with no data (no API call should be made)"""
        alert_data = None
        recipients = ['test@example.com']
        
        result = self.email_service.send_monthly_built_area(recipients, alert_data)
        self.assertFalse(result)
        # Should not call Graph API when there's no data
        mock_post.assert_not_called()
        mock_get_token.assert_not_called()

    @patch('src.email_service.requests.post')
    @patch.object(EmailService, '_get_access_token')
    def test_send_weekly_report_renders_metadata_file_links(self, mock_get_token, mock_post):
        """Weekly report should include file links from DB metadata and convert gs:// URLs."""
        mock_get_token.return_value = 'fake-access-token'

        mock_response = Mock()
        mock_response.status_code = 202
        mock_response.text = ''
        mock_post.return_value = mock_response

        weekly_report = {
            'report_title': 'Alertas GFW - Semana',
            'report_url': 'gs://reportes-simbyp/reportes_gfw/semana_2026-06-01_a_2026-06-07/reporte_final.html',
            'report_date': '2026-06-07',
            'metadata': {
                'start_date': '2026-06-01',
                'end_date': '2026-06-07',
                'files': [
                    {'name': 'Reporte Principal', 'url': 'gs://reportes-simbyp/reportes_gfw/semana_2026-06-01_a_2026-06-07/reporte_final.html'},
                    {'name': 'GeoJSON', 'path': 'output.geojson'}
                ]
            }
        }

        recipients = ['test@example.com']
        result = self.email_service.send_weekly_report(recipients, weekly_report)

        self.assertTrue(result)
        mock_post.assert_called_once()

        request_payload = mock_post.call_args.kwargs['json']
        html_content = request_payload['message']['body']['content']

        self.assertIn('Reporte Principal', html_content)
        self.assertIn('GeoJSON', html_content)
        self.assertIn('https://storage.googleapis.com/reportes-simbyp/reportes_gfw/semana_2026-06-01_a_2026-06-07/reporte_final.html', html_content)
        self.assertIn('https://storage.googleapis.com/reportes-simbyp/reportes_gfw/semana_2026-06-01_a_2026-06-07/output.geojson', html_content)

    @patch('src.email_service.requests.post')
    @patch.object(EmailService, '_get_access_token')
    def test_send_monthly_report_renders_metadata_file_links(self, mock_get_token, mock_post):
        """Monthly report should include metadata-driven file names and links."""
        mock_get_token.return_value = 'fake-access-token'

        mock_response = Mock()
        mock_response.status_code = 202
        mock_response.text = ''
        mock_post.return_value = mock_response

        monthly_report = {
            'report_title': 'Area Construida - Mayo',
            'report_url': 'gs://reportes-simbyp/urban_sprawl/urban_sprawl_reporte_2026_Mayo.html',
            'report_date': '2026-05-31',
            'metadata': {
                'files': [
                    {'name': 'Reporte Mensual', 'url': 'gs://reportes-simbyp/urban_sprawl/urban_sprawl_reporte_2026_Mayo.html'},
                    {'name': 'Tabla Resumen', 'path': 'urban_sprawl_reporte.json'}
                ]
            }
        }

        recipients = ['test@example.com']
        result = self.email_service.send_monthly_built_area(recipients, monthly_report)

        self.assertTrue(result)
        mock_post.assert_called_once()

        request_payload = mock_post.call_args.kwargs['json']
        html_content = request_payload['message']['body']['content']

        self.assertIn('Reporte Mensual', html_content)
        self.assertIn('Tabla Resumen', html_content)
        self.assertIn('https://storage.googleapis.com/reportes-simbyp/urban_sprawl/urban_sprawl_reporte_2026_Mayo.html', html_content)
        self.assertIn('https://storage.googleapis.com/reportes-simbyp/urban_sprawl/urban_sprawl_reporte.json', html_content)

if __name__ == '__main__':
    unittest.main()
