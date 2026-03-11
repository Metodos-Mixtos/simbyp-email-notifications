import os
import csv
import io
import logging
from google.cloud import storage

# Load .env file only if it exists (for local development)
# GCP Cloud Run provides environment variables directly
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

logger = logging.getLogger(__name__)

# ============================================================================
# APPLICATION DEFAULTS
# These are the standard values used across environments.
# Override them by setting environment variables if needed.
# ============================================================================

# GCP Configuration
GCP_PROJECT_ID = os.getenv('GCP_PROJECT_ID', 'bosques-bogota-416214')

# Email Configuration - Default values for SIMBYP alerts
FROM_EMAIL = os.getenv('FROM_EMAIL', 'simbyp@sdp.gov.co')
FROM_NAME = os.getenv('FROM_NAME', 'SIMBYP Alertas')
RECIPIENTS_CSV_URI = os.getenv('RECIPIENTS_CSV_URI', 'gs://material-estatico-sdp/SIMBYP_DATA/listas_distribucion/lista_circulacion_reportes - test.csv').strip()

# Service Configuration
DAYS_BACK = int(os.getenv('DAYS_BACK', 20))
PORT = int(os.getenv('PORT', 8080))

# ============================================================================
# SECRETS & ENVIRONMENT-SPECIFIC
# These MUST be set as environment variables or in .env (for local dev only)
# ============================================================================

SENDGRID_API_KEY = os.getenv('SENDGRID_API_KEY')

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

# GCS Configuration (bucket names and object prefixes)
GCS_BUCKETS = {
    'reports': 'reportes-simbyp',
}

GCS_PREFIXES = {
    'gfw': 'reportes_gfw/',
    'psa': 'reportes_psa/',
    'area_construida': 'urban_sprawl/',
    'weekly_alerts': 'reportes_gfw/semana_',
}


# Validation for required environment variables
def _validate_config():
    """Validate that all required configuration is set."""
    errors = []
    
    if not SENDGRID_API_KEY:
        errors.append("SENDGRID_API_KEY is not set")
    
    if not RECIPIENTS_CSV_URI:
        if not any(RECIPIENTS.values()):
            errors.append("No recipients configured. Set RECIPIENTS_CSV_URI or WEEKLY_ALERTS_RECIPIENTS/MONTHLY_BUILT_AREA_RECIPIENTS")
    
    if errors:
        error_msg = "Configuration errors:\n  - " + "\n  - ".join(errors)
        logger.error(error_msg)
        raise ValueError(error_msg)


# Validate config on import (can be disabled for testing)
if os.getenv('VALIDATE_CONFIG', 'true').lower() == 'true':
    _validate_config()