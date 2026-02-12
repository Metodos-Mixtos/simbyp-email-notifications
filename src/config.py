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
    'area_construida': 'reportes_area_construida/',
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
        "gfw_alerts": [],
        "psa_reports": [],
        "area_construida": [],
        "weekly_digest": [],
    }
    if not csv_text:
        return groups
    reader = csv.DictReader(io.StringIO(csv_text))
    for row in reader:
        email = row.get("Correo", "").strip()
        if not email:
            continue
        if row.get("reporte_gfw") == "1":
            groups["gfw_alerts"].append(email)
        if row.get("reporte_paramos") == "1":
            groups["psa_reports"].append(email)
        if row.get("reporte_area_construida") == "1":
            groups["area_construida"].append(email)
        if row.get("weekly_digest") == "1":
            groups["weekly_digest"].append(email)
    return groups

# Load recipients from CSV, fallback to env vars
RECIPIENTS = _build_distribution_lists(_download_recipients_csv())
if not any(RECIPIENTS.values()):
    RECIPIENTS = {
        "gfw_alerts": _split_env_list(os.getenv("GFW_RECIPIENTS", "")),
        "psa_reports": _split_env_list(os.getenv("PSA_RECIPIENTS", "")),
        "area_construida": _split_env_list(os.getenv("AREA_CONSTRUIDA_RECIPIENTS", "")),
        "weekly_digest": _split_env_list(os.getenv("DIGEST_RECIPIENTS", "")),
    }

# Email Configuration
SENDGRID_API_KEY = os.getenv('SENDGRID_API_KEY')
FROM_EMAIL = os.getenv('FROM_EMAIL', 'alerts@simbyp.org')
FROM_NAME = os.getenv('FROM_NAME', 'SIMBYP Alertas')

# Service Configuration
DAYS_BACK = int(os.getenv('DAYS_BACK', 7))
PORT = int(os.getenv('PORT', 8080))