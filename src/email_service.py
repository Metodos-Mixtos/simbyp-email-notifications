import os
import logging
from datetime import datetime
from typing import List, Dict, Any
from urllib.parse import urljoin
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

    def _to_public_url(self, path_or_url: str) -> str:
        """Convert GCS URI to HTTPS URL and keep HTTP URLs unchanged."""
        if not path_or_url:
            return path_or_url

        value = str(path_or_url).strip()
        if value.startswith('http://') or value.startswith('https://'):
            return value

        if value.startswith('gs://'):
            # gs://bucket/path/to/file -> https://storage.googleapis.com/bucket/path/to/file
            gcs_path = value[5:]
            parts = gcs_path.split('/', 1)
            bucket = parts[0]
            obj_path = parts[1] if len(parts) > 1 else ''
            return f"https://storage.googleapis.com/{bucket}/{obj_path}"

        return value

    def _resolve_file_url(self, file_ref: str, report_url: str) -> str | None:
        """Resolve file references from metadata to full URLs."""
        if not file_ref:
            return None

        ref = str(file_ref).strip()
        if ref.startswith('http://') or ref.startswith('https://') or ref.startswith('gs://'):
            return self._to_public_url(ref)

        if not report_url:
            return None

        base = str(report_url).strip()
        if base.startswith('gs://'):
            base_dir = base.rsplit('/', 1)[0]
            ref_path = ref.lstrip('/')
            if '/' in ref_path:
                # Already includes directory path under bucket
                return self._to_public_url(f"gs://{base[5:].split('/', 1)[0]}/{ref_path}")
            return self._to_public_url(f"{base_dir}/{ref_path}")

        if base.startswith('http://') or base.startswith('https://'):
            base_dir = base.rsplit('/', 1)[0] + '/'
            return urljoin(base_dir, ref)

        return None

    def _extract_file_links(self, metadata: Dict[str, Any], report_url: str) -> List[Dict[str, str]]:
        """Extract and normalize report file links from metadata JSON."""
        if not isinstance(metadata, dict):
            return []

        candidates = []
        for key in ('files', 'report_files', 'file_links', 'email_files'):
            value = metadata.get(key)
            if isinstance(value, list):
                candidates.extend(value)

        files = []
        seen_urls = set()
        for item in candidates:
            raw_ref = None
            file_name = None

            if isinstance(item, str):
                raw_ref = item
            elif isinstance(item, dict):
                raw_ref = (
                    item.get('url')
                    or item.get('public_url')
                    or item.get('path')
                    or item.get('gcs_path')
                    or item.get('object_path')
                )
                file_name = item.get('name') or item.get('title') or item.get('label')

            resolved_url = self._resolve_file_url(raw_ref, report_url)
            if not resolved_url:
                continue

            if not file_name:
                file_name = str(raw_ref).rstrip('/').split('/')[-1]

            if resolved_url in seen_urls:
                continue

            files.append({'name': file_name, 'url': resolved_url})
            seen_urls.add(resolved_url)

        return files

    def _normalize_report_payload(self, report_data: Dict[str, Any], default_title: str) -> Dict[str, Any]:
        """Normalize bucket-based and DB-based report payloads into one template contract."""
        metadata = report_data.get('metadata') or report_data.get('metadata_json') or {}
        report_url_raw = report_data.get('report_url') or report_data.get('url')
        report_url = self._to_public_url(report_url_raw) if report_url_raw else None

        updated = report_data.get('updated') or report_data.get('sent_at') or datetime.utcnow()
        if isinstance(updated, str):
            try:
                updated = datetime.fromisoformat(updated.replace('Z', '+00:00'))
            except ValueError:
                updated = datetime.utcnow()

        report_name = report_data.get('report_name')
        if not report_name and report_url_raw:
            report_name = str(report_url_raw).rstrip('/').split('/')[-1]

        start_date = report_data.get('start_date') or metadata.get('start_date')
        end_date = report_data.get('end_date') or metadata.get('end_date')
        report_date = report_data.get('report_date')

        files = self._extract_file_links(metadata, report_url_raw)
        if not files and report_url:
            files.append({'name': report_name or 'reporte_final.html', 'url': report_url})

        return {
            'title': report_data.get('title') or report_data.get('report_title') or default_title,
            'url': report_url,
            'report_name': report_name,
            'updated': updated,
            'start_date': start_date,
            'end_date': end_date or report_date,
            'report_date': report_date,
            'top_upls': metadata.get('top_upls', []),
            'files': files,
            'metadata': metadata,
        }
    
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

        report = self._normalize_report_payload(
            weekly_report,
            default_title='Reporte Semanal de Alertas SIMBYP'
        )
        
        template = self.jinja_env.get_template('weekly_report.html')
        
        html_content = template.render(
            report=report
        )

        period_start = report.get('start_date') or 'N/A'
        period_end = report.get('end_date') or 'N/A'
        subject = f"Reporte Semanal de Alertas SIMBYP - {period_start} a {period_end}"
        
        return self.send_email(recipients, subject, html_content)
    
    def send_monthly_built_area(self, recipients: List[str], alert_data: Dict) -> bool:
        """Send monthly built area alert email with UPL expansion data"""
        if not alert_data:
            logger.info("No built area alerts to send")
            return False

        report = self._normalize_report_payload(
            alert_data,
            default_title='Reporte Mensual - Alertas de Área Construida SIMBYP'
        )
        
        template = self.jinja_env.get_template('built_area_alert.html')
        top_upls = report.get('top_upls') or []

        html_content = template.render(
            report=report,
            has_upls=bool(top_upls),
            top_upls=top_upls,
            alert=report
        )
        
        subject = f"Reporte Mensual - Alertas de Área Construida SIMBYP"
        
        return self.send_email(recipients, subject, html_content)