from typing import List, Dict, Optional
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
    
    def get_latest_weekly_alerts_report(self) -> Optional[Dict]:
        """
        Fetch the latest weekly alerts report from GCS.
        Expected format: reportes_gfw/semana_YYYY-MM-DD_a_YYYY-MM-DD/reporte_final.html
        Returns report info or None if not found
        """
        try:
            prefix = GCS_PREFIXES['weekly_alerts']
            logger.info(f"Searching for weekly reports with prefix: {prefix}")
            all_objects = self.gcs.list_all_objects(self.bucket, prefix)
            logger.info(f"Found {len(all_objects)} total objects with prefix {prefix}")
            
            # Log first 10 objects found
            for i, obj in enumerate(all_objects[:10]):
                logger.info(f"  Object {i+1}: {obj['name']}")
            
            # Filter for HTML files within semana_ directories
            # Expected pattern: reportes_gfw/semana_YYYY-MM-DD_a_YYYY-MM-DD/reporte_final.html
            report_files = [
                obj for obj in all_objects
                if obj['name'].endswith('.html')
            ]
            
            logger.info(f"Found {len(report_files)} HTML files")
            for i, obj in enumerate(report_files[:5]):
                logger.info(f"  Report {i+1}: {obj['name']}")
            
            if not report_files:
                logger.info("No weekly alerts reports found")
                return None
            
            # Get the latest report (already sorted by updated time descending)
            latest_report = report_files[0]
            
            # Extract dates from the folder name
            # Format: reportes_gfw/semana_YYYY-MM-DD_a_YYYY-MM-DD/reporte_final.html
            match = re.search(r'semana_(\d{4}-\d{2}-\d{2})_a_(\d{4}-\d{2}-\d{2})', latest_report['name'])
            
            if match:
                start_date, end_date = match.groups()
                report_info = {
                    'type': 'weekly_alerts_report',
                    'report_name': latest_report['name'].split('/')[-1],
                    'updated': latest_report['updated'],
                    'url': latest_report['public_url'],
                    'start_date': start_date,
                    'end_date': end_date,
                    'title': f"Reporte de Alertas Semanales - {start_date} a {end_date}"
                }
                logger.info(f"Found latest weekly alerts report: {latest_report['name']}")
                return report_info
            else:
                logger.warning(f"Could not extract dates from report name: {latest_report['name']}")
                return None
        
        except Exception as e:
            logger.error(f"Error getting latest weekly alerts report: {str(e)}")
            return None
    
    def get_area_construida_alerts(self, days_back: int) -> List[Dict]:
        """Get built area alerts - returns latest urban_sprawl_reporte and its data"""
        prefix = GCS_PREFIXES.get('area_construida', 'urban_sprawl/')
        reports = self.gcs.list_recent_reports(self.bucket, prefix, days_back)
        
        # Filter for only urban_sprawl_reporte_*.html files
        filtered_reports = [r for r in reports if 'urban_sprawl_reporte_' in r['name'] and r['name'].endswith('.html')]
        
        if not filtered_reports:
            logger.info("No urban_sprawl_reporte files found")
            return []
        
        # Sort by filename date (YYYY_MESNAME) to get the latest report
        # Expected format: urban_sprawl_reporte_YYYY_MESNAME.html
        def extract_date_from_filename(report):
            filename = report['name'].split('/')[-1]
            # Extract YYYY_MESNAME from urban_sprawl_reporte_YYYY_MESNAME.html
            match = re.search(r'(\d{4})_(\w+)', filename)
            if match:
                year, month = match.groups()
                # Create sortable key: year as int + month name (alphabetically)
                # We'll use month_name for sorting, with year priority
                return (int(year), month)
            return (0, '')
        
        # Sort by year (desc) then by month name for reports in same year
        months_order = {
            'Enero': 1, 'Febrero': 2, 'Marzo': 3, 'Abril': 4, 'Mayo': 5,
            'Junio': 6, 'Julio': 7, 'Agosto': 8, 'Septiembre': 9,
            'Octubre': 10, 'Noviembre': 11, 'Diciembre': 12
        }
        
        def sort_key(report):
            year, month = extract_date_from_filename(report)
            month_num = months_order.get(month, 0)
            return (year, month_num)
        
        sorted_reports = sorted(filtered_reports, key=sort_key, reverse=True)
        latest_report = sorted_reports[0]
        
        logger.info(f"Selected latest report: {latest_report['name']}")
        
        # Try to find and read the JSON data file in the same directory
        report_dir = '/'.join(latest_report['name'].split('/')[:-1])
        json_file_path = f"{report_dir}/urban_sprawl_reporte.json"
        
        logger.info(f"Looking for JSON file at: {json_file_path}")
        json_data = self.gcs.download_json(self.bucket, json_file_path)
        
        # Extract TOP_UPLS from JSON
        top_upls = json_data.get('TOP_UPLS', []) if json_data else []
        
        alert = {
            'type': 'area_construida',
            'report_name': latest_report['name'].split('/')[-1],
            'updated': latest_report['updated'],
            'url': latest_report['public_url'],
            'title': "Reporte Mensual de Área Construida",
            'top_upls': top_upls
        }
        
        return [alert]