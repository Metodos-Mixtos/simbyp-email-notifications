import os
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail, Email, To, Content, Bcc
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
    
    def send_weekly_alerts(self, recipients: List[str], alerts: Dict[str, List], weekly_report: Dict = None) -> bool:
        """Send weekly alerts email (deforestation + land_cover) with optional weekly report"""
        if not any(alerts.values()) and not weekly_report:
            logger.info("No weekly alerts or report to send")
            return False
        
        template = self.jinja_env.get_template('weekly_alerts.html')
        
        deforestation_count = len(alerts.get('deforestation', []))
        land_cover_count = len(alerts.get('land_cover', []))
        total_count = deforestation_count + land_cover_count
        
        html_content = template.render(
            alerts=alerts,
            deforestation_count=deforestation_count,
            land_cover_count=land_cover_count,
            total_count=total_count,
            has_alerts=total_count > 0,
            weekly_report=weekly_report,
            has_report=weekly_report is not None
        )
        
        subject = f"Alertas Semanales SIMBYP - Deforestación y Cambios de Cobertura"
        
        return self.send_email(recipients, subject, html_content)
    
    def send_weekly_report(self, recipients: List[str], weekly_report: Dict) -> bool:
        """Send weekly alerts report email (direct link to HTML report)"""
        if not weekly_report:
            logger.info("No weekly report to send")
            return False
        
        template = self.jinja_env.get_template('weekly_report.html')
        
        html_content = template.render(
            report=weekly_report
        )
        
        subject = f"Reporte Semanal de Alertas SIMBYP - {weekly_report['start_date']} a {weekly_report['end_date']}"
        
        return self.send_email(recipients, subject, html_content)
    
    def send_monthly_built_area(self, recipients: List[str], alert_data: Dict) -> bool:
        """Send monthly built area alert email with UPL expansion data"""
        if not alert_data:
            logger.info("No built area alerts to send")
            return False
        
        template = self.jinja_env.get_template('built_area_alert.html')
        
        # Extract UPL data from alert
        top_upls = alert_data.get('top_upls', [])
        
        html_content = template.render(
            alert=alert_data,
            top_upls=top_upls,
            has_upls=len(top_upls) > 0
        )
        
        subject = f"Reporte Mensual de Área Construida - SIMBYP"
        
        return self.send_email(recipients, subject, html_content)
    
    def send_email(self, subject, html_content, recipients):
        """
        Send email to recipients using BCC to hide recipient list.
        
        Args:
            subject: Email subject
            html_content: HTML email body
            recipients: List of email addresses
        """
        message = Mail(
            from_email=FROM_EMAIL,
            to_emails=FROM_EMAIL,  # Send to self, recipients in BCC
            subject=subject,
            html_content=html_content,
        )
        
        # Add all recipients to BCC (hidden from each other)
        for recipient in recipients:
            message.bcc.add(Bcc(recipient))
        
        try:
            sg = SendGridAPIClient(SENDGRID_API_KEY)
            response = sg.send(message)
            logger.info(f"Email sent successfully. Status: {response.status_code}")
            return response
        except Exception as e:
            logger.error(f"Error sending email: {e}")
            raise