import os
from dotenv import load_dotenv
import csv
import io
import logging
from google.cloud import storage

load_dotenv()
logger = logging.getLogger(__name__)

# GCP Configuration
GCP_PROJECT_ID = os.getenv('GCP_PROJECT_ID', 'your-project-id')

# GCS Configuration
GCS_BUCKETS = {
    'reports': 'reportes-simbyp',
}

GCS_PREFIXES = {
    'gfw': 'reportes_gfw/',
    'psa': 'reportes_psa/',
    'area_construida': 'urban_sprawl/',
}


RECIPIENTS_CSV_URI = os.getenv("RECIPIENTS_CSV_URI", "").strip()

def _split_env_list(raw: str) -> list[str]:
    return [item.strip() for item in raw.split(",") if item.strip()]

def _download_recipients_csv() -> str | None:
    if not RECIPIENTS_CSV_URI:
        return None
    if not RECIPIENTS_CSV_URI.startswith("gs://"):
        logger.error("RECIPIENTS_CSV_URI must start with gs://")
        return None
    bucket_name, blob_name = RECIPIENTS_CSV_URI[5:].split("/", 1)
    client = storage.Client()
    blob = client.bucket(bucket_name).blob(blob_name)
    return blob.download_as_text(encoding="utf-8")

def _build_distribution_lists(csv_text: str | None) -> dict[str, list[str]]:
    groups = {
        "weekly_alerts_recipients": [],
        "monthly_built_area_recipients": [],
    }
    if not csv_text:
        return groups
    reader = csv.DictReader(io.StringIO(csv_text))
    for row in reader:
        email = row.get("Correo", "").strip()
        if not email:
            continue
        if row.get("weekly_alerts") == "1":
            groups["weekly_alerts_recipients"].append(email)
        if row.get("monthly_built_area") == "1":
            groups["monthly_built_area_recipients"].append(email)
    return groups

# Load recipients from CSV, fallback to env vars
RECIPIENTS = _build_distribution_lists(_download_recipients_csv())
if not any(RECIPIENTS.values()):
    RECIPIENTS = {
        "weekly_alerts_recipients": _split_env_list(os.getenv("WEEKLY_ALERTS_RECIPIENTS", "")),
        "monthly_built_area_recipients": _split_env_list(os.getenv("MONTHLY_BUILT_AREA_RECIPIENTS", "")),
    }

# Email Configuration
SENDGRID_API_KEY = os.getenv('SENDGRID_API_KEY')
FROM_EMAIL = os.getenv('FROM_EMAIL', 'alerts@simbyp.org')
FROM_NAME = os.getenv('FROM_NAME', 'SIMBYP Alertas')

# Service Configuration
DAYS_BACK = int(os.getenv('DAYS_BACK', 7))
PORT = int(os.getenv('PORT', 8080))