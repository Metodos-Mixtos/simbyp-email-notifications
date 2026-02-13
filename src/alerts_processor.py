from typing import List, Dict
import logging
from datetime import datetime
import re
from src.gcs_handler import GCSHandler
from src.config import GCS_BUCKETS, GCS_PREFIXES, DAYS_BACK

logger = logging.getLogger(__name__)

class AlertProcessor:
    def __init__(self, gcs_handler: GCSHandler):
        self.gcs = gcs_handler
        self.bucket = GCS_BUCKETS['reports']
    
    def get_weekly_alerts(self, days_back: int = DAYS_BACK) -> Dict[str, List]:
        """Get weekly alerts: deforestation (GFW) + land cover (PSA)"""
        logger.info(f"Fetching weekly alerts from the last {days_back} days")
        
        alerts = {
            'deforestation': self.get_gfw_alerts(days_back),
            'land_cover': self.get_psa_reports(days_back),
        }
        
        total_alerts = sum(len(v) for v in alerts.values())
        logger.info(f"Total weekly alerts found: {total_alerts}")
        
        return alerts
    
    def get_monthly_built_area(self, days_back: int = DAYS_BACK) -> List[Dict]:
        """Get monthly built area alerts"""
        logger.info(f"Fetching built area alerts from the last {days_back} days")
        
        alerts = self.get_area_construida_alerts(days_back)
        logger.info(f"Total built area alerts found: {len(alerts)}")
        
        return alerts
    
    def get_gfw_alerts(self, days_back: int) -> List[Dict]:
        """Get GFW deforestation alerts"""
        prefix = GCS_PREFIXES['gfw']
        reports = self.gcs.list_recent_reports(self.bucket, prefix, days_back)
        
        processed_alerts = []
        for report in reports:
            # Extract trimestre and año from path
            # Expected format: reportes_gfw/I_trim_2026/reporte_final.html
            match = re.search(r'(\w+)_trim_(\d{4})', report['name'])
            
            if match:
                trimestre, anio = match.groups()
                alert = {
                    'type': 'gfw_deforestation',
                    'trimestre': trimestre,
                    'anio': anio,
                    'report_name': report['name'].split('/')[-1],
                    'updated': report['updated'],
                    'url': report['public_url'],
                    'title': f"Alertas GFW - {trimestre} Trimestre {anio}"
                }
                processed_alerts.append(alert)
        
        return processed_alerts
    
    def get_psa_reports(self, days_back: int) -> List[Dict]:
        """Get PSA reports (land cover / paramo)"""
        prefix = GCS_PREFIXES['psa']
        reports = self.gcs.list_recent_reports(self.bucket, prefix, days_back)
        
        processed_reports = []
        for report in reports:
            # Extract codigo_predio from path
            # Expected format: reportes_psa/{codigo_predio}/reporte_*.html
            path_parts = report['name'].split('/')
            
            if len(path_parts) >= 2:
                codigo_predio = path_parts[1]
                alert = {
                    'type': 'psa_report',
                    'codigo_predio': codigo_predio,
                    'report_name': report['name'].split('/')[-1],
                    'updated': report['updated'],
                    'url': report['public_url'],
                    'title': f"Reporte PSA - Predio {codigo_predio}"
                }
                processed_reports.append(alert)
        
        return processed_reports
    
    def get_area_construida_alerts(self, days_back: int) -> List[Dict]:
        """Get built area alerts"""
        prefix = GCS_PREFIXES.get('area_construida', 'reportes_area_construida/')
        reports = self.gcs.list_recent_reports(self.bucket, prefix, days_back)
        
        processed_alerts = []
        for report in reports:
            alert = {
                'type': 'area_construida',
                'report_name': report['name'].split('/')[-1],
                'updated': report['updated'],
                'url': report['public_url'],
                'title': "Alerta de Área Construida"
            }
            processed_alerts.append(alert)
        
        return processed_alerts