from google.cloud import storage
from datetime import datetime, timedelta, timezone
from typing import List, Dict
import logging

logger = logging.getLogger(__name__)

class GCSHandler:
    def __init__(self, project_id: str):
        self.client = storage.Client(project=project_id)
    
    def list_recent_reports(self, bucket_name: str, prefix: str, days_back: int = 7) -> List[Dict]:
        """List HTML reports from the last N days"""
        try:
            bucket = self.client.bucket(bucket_name)
            blobs = bucket.list_blobs(prefix=prefix)
            
            cutoff = datetime.now(timezone.utc) - timedelta(days=days_back)
            recent_reports = []
            
            for blob in blobs:
                # Filter for HTML files updated within the timeframe
                if blob.name.endswith('.html') and blob.updated and blob.updated >= cutoff:
                    report_info = {
                        'name': blob.name,
                        'path': f"gs://{bucket_name}/{blob.name}",
                        'public_url': self._get_public_url(bucket_name, blob.name),
                        'updated': blob.updated,
                        'size': blob.size,
                    }
                    recent_reports.append(report_info)
            
            logger.info(f"Found {len(recent_reports)} reports in {bucket_name}/{prefix}")
            return sorted(recent_reports, key=lambda x: x['updated'], reverse=True)
        
        except Exception as e:
            logger.error(f"Error listing reports from {bucket_name}/{prefix}: {str(e)}")
            return []
    
    def _get_public_url(self, bucket_name: str, blob_name: str) -> str:
        """Generate public URL for a GCS object"""
        return f"https://storage.googleapis.com/{bucket_name}/{blob_name}"
    
    def make_blob_public(self, bucket_name: str, blob_name: str) -> str:
        """Make a blob publicly readable and return its URL"""
        try:
            bucket = self.client.bucket(bucket_name)
            blob = bucket.blob(blob_name)
            blob.make_public()
            logger.info(f"Made {blob_name} public")
            return blob.public_url
        except Exception as e:
            logger.error(f"Error making {blob_name} public: {str(e)}")
            return self._get_public_url(bucket_name, blob_name)
    
    def get_blob_metadata(self, bucket_name: str, blob_name: str) -> Dict:
        """Get metadata for a specific blob"""
        try:
            bucket = self.client.bucket(bucket_name)
            blob = bucket.blob(blob_name)
            blob.reload()
            
            return {
                'name': blob.name,
                'size': blob.size,
                'updated': blob.updated,
                'content_type': blob.content_type,
                'public_url': self._get_public_url(bucket_name, blob.name)
            }
        except Exception as e:
            logger.error(f"Error getting metadata for {blob_name}: {str(e)}")
            return {}