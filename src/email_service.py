import os
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail, Email, To, Content
from jinja2 import Environment, FileSystemLoader
import logging
from typing import List, Dict

from src.config import SENDGRID_API_KEY, FROM_EMAIL, FROM_NAME

logger = logging.getLogger(__name__)

class EmailService:
    def __init__(self):
        self.api_key = SENDGRID_API_KEY
        self.from_email = FROM_EMAIL
        self.from_name = FROM_NAME
        
        # Setup Jinja2 for templates
        template_dir = os.path.join(os.path.dirname(__file__), 'templates')
        self.jinja_env = Environment(loader=FileSystemLoader(template_dir))
    
    def send_email(self, recipients: List[str], subject: str, html_content: str) -> bool:
        """Send email using SendGrid"""
        if not self.api_key:
            logger.error("SendGrid API key not configured")
            return False
        
        if not recipients:
            logger.warning("No recipients specified")
            return False
        
        try:
            message = Mail(
                from_email=Email(self.from_email, self.from_name),
                to_emails=[To(email) for email in recipients],
                subject=subject,
                html_content=Content("text/html", html_content)
            )
            
            sg = SendGridAPIClient(self.api_key)
            response = sg.send(message)
            
            logger.info(f"Email sent successfully. Status: {response.status_code}")
            logger.info(f"Recipients: {', '.join(recipients)}")
            return True
        
        except Exception as e:
            logger.error(f"Error sending email: {str(e)}")
            return False
    
    def send_alert_email(self, recipient: str, subject: str, body: str) -> bool:
        """Send a simple alert email (legacy method for backwards compatibility)."""
        if not recipient or not recipient.strip():
            logger.warning("No recipient specified")
            return False
        return self.send_email([recipient.strip()], subject, body)

    def send_weekly_digest(self, recipients: List[str], alerts: Dict[str, List], summary: Dict) -> bool:
        """Send weekly digest email"""
        template = self.jinja_env.get_template('weekly_digest.html')
        
        html_content = template.render(
            alerts=alerts,
            summary=summary,
            has_alerts=summary['total_alerts'] > 0
        )
        
        subject = f"📊 Resumen Semanal SIMBYP - {summary['generated_at']}"
        
        return self.send_email(recipients, subject, html_content)
    
    def send_gfw_alert(self, recipients: List[str], alert_data: Dict) -> bool:
        """Send individual GFW alert email"""
        template = self.jinja_env.get_template('deforestation_alert.html')
        
        html_content = template.render(alert=alert_data)
        
        subject = f"🌳 {alert_data['title']}"
        
        return self.send_email(recipients, subject, html_content)