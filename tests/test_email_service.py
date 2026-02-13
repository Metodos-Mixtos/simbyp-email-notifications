import unittest
from unittest.mock import patch, MagicMock
from datetime import datetime
from src.email_service import EmailService

class TestEmailService(unittest.TestCase):

    def setUp(self):
        self.email_service = EmailService()

    @patch('src.email_service.SendGridAPIClient')
    def test_send_weekly_alerts(self, mock_sg_client):
        """Test sending weekly alerts email"""
        mock_response = MagicMock()
        mock_response.status_code = 202
        mock_sg_client.return_value.send.return_value = mock_response
        
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
        mock_sg_client.return_value.send.assert_called_once()

    @patch('src.email_service.SendGridAPIClient')
    def test_send_weekly_alerts_no_data(self, mock_sg_client):
        """Test weekly alerts with no data"""
        alerts = {
            'deforestation': [],
            'land_cover': []
        }
        recipients = ['test@example.com']
        
        result = self.email_service.send_weekly_alerts(recipients, alerts)
        self.assertFalse(result)
        mock_sg_client.return_value.send.assert_not_called()

    @patch('src.email_service.SendGridAPIClient')
    def test_send_monthly_built_area(self, mock_sg_client):
        """Test sending monthly built area email"""
        mock_response = MagicMock()
        mock_response.status_code = 202
        mock_sg_client.return_value.send.return_value = mock_response
        
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
        mock_sg_client.return_value.send.assert_called_once()

    @patch('src.email_service.SendGridAPIClient')
    def test_send_monthly_built_area_no_data(self, mock_sg_client):
        """Test monthly built area with no data"""
        alert_data = None
        recipients = ['test@example.com']
        
        result = self.email_service.send_monthly_built_area(recipients, alert_data)
        self.assertFalse(result)
        mock_sg_client.return_value.send.assert_not_called()

if __name__ == '__main__':
    unittest.main()
