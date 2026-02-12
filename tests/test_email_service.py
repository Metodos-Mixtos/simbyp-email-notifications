import unittest
from unittest.mock import patch, MagicMock
from src.email_service import EmailService

class TestEmailService(unittest.TestCase):

    def setUp(self):
        self.email_service = EmailService()

    @patch('src.email_service.SendGridAPIClient')
    def test_send_alert_email(self, mock_sg_client):
        """Test sending a simple alert email"""
        mock_response = MagicMock()
        mock_response.status_code = 202
        mock_sg_client.return_value.send.return_value = mock_response
        
        recipient = "test@example.com"
        subject = "Test Alert"
        body = "This is a test alert email."
        
        result = self.email_service.send_alert_email(recipient, subject, body)
        self.assertTrue(result)
        mock_sg_client.return_value.send.assert_called_once()

    @patch('src.email_service.SendGridAPIClient')
    def test_send_alert_email_no_recipients(self, mock_sg_client):
        """Test sending alert with empty recipient list"""
        recipient = ""
        subject = "Test Alert"
        body = "This is a test alert email."
        
        result = self.email_service.send_alert_email(recipient, subject, body)
        # Empty recipient should be handled gracefully
        self.assertFalse(result)

    @patch('src.email_service.SendGridAPIClient')
    def test_send_alert_email_sendgrid_error(self, mock_sg_client):
        """Test handling of SendGrid API errors"""
        mock_sg_client.return_value.send.side_effect = Exception("SendGrid error")
        
        recipient = "test@example.com"
        subject = "Test Alert"
        body = "This is a test alert email."
        
        result = self.email_service.send_alert_email(recipient, subject, body)
        self.assertFalse(result)

if __name__ == '__main__':
    unittest.main()