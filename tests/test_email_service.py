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

if __name__ == '__main__':
    unittest.main()
