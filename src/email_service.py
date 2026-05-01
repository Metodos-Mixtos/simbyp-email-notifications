import os
import logging
from typing import List, Dict
from jinja2 import Environment, FileSystemLoader
import requests
from azure.identity import ClientSecretCredential

logger = logging.getLogger(__name__)

class EmailService:
    def __init__(self, client_id: str, tenant_id: str, client_secret: str, from_email: str, from_name: str):
        """Initialize Microsoft Graph email service using service account (app credentials)."""
        self.from_email = from_email
        self.from_name = from_name
        self.client_id = client_id
        self.tenant_id = tenant_id
        self.client_secret = client_secret
        
        # Setup Jinja2 for templates
        template_dir = os.path.join(os.path.dirname(__file__), 'templates')
        self.jinja_env = Environment(loader=FileSystemLoader(template_dir))
        
        # Initialize Azure credentials
        self.credential = ClientSecretCredential(
            tenant_id=tenant_id,
            client_id=client_id,
            client_secret=client_secret
        )
        logger.info(f"EmailService initialized with from_email: {from_email}")
    
    def _get_access_token(self) -> str | None:
        """Get access token from Azure AD."""
        try:
            token = self.credential.get_token("https://graph.microsoft.com/.default")
            logger.debug("Successfully obtained Azure AD access token")
            return token.token
        except Exception as e:
            logger.error(f"Failed to get access token: {str(e)}")
            return None
    
    def send_email(self, recipients: List[str], subject: str, html_content: str) -> bool:
        """Send email to recipients using Microsoft Graph API with BCC to hide recipient list."""
        if not recipients:
            logger.warning("No recipients specified")
            return False
        
        try:
            access_token = self._get_access_token()
            if not access_token:
                logger.error("Failed to obtain access token for Microsoft Graph")
                return False
            
            # Microsoft Graph API endpoint
            url = f"https://graph.microsoft.com/v1.0/users/{self.from_email}/sendMail"
            
            # Prepare email body with BCC recipients to hide them from each other
            email_body = {
                "message": {
                    "subject": subject,
                    "body": {
                        "contentType": "HTML",
                        "content": html_content
                    },
                    "from": {
                        "emailAddress": {
                            "address": self.from_email,
                            "name": self.from_name
                        }
                    },
                    "toRecipients": [
                        {
                            "emailAddress": {
                                "address": self.from_email,
                                "name": self.from_name
                            }
                        }
                    ],
                    "bccRecipients": [
                        {
                            "emailAddress": {
                                "address": recipient
                            }
                        } for recipient in recipients
                    ]
                },
                "saveToSentItems": True
            }
            
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json"
            }
            
            response = requests.post(url, json=email_body, headers=headers)
            
            if response.status_code == 202:
                logger.info(f"Email sent successfully to {len(recipients)} recipients (BCC)")
                logger.info(f"Recipients (BCC): {', '.join(recipients)}")
                return True
            else:
                logger.error(f"Failed to send email: HTTP {response.status_code}")
                logger.error(f"Response: {response.text}")
                return False
        
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
        
        html_content = template.render(
            alert_data=alert_data
        )
        
        subject = f"Reporte Mensual - Alertas de Área Construida SIMBYP"
        
        return self.send_email(recipients, subject, html_content)