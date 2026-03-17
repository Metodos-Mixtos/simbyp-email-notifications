import os
import logging
import csv
import io
from google.cloud import storage
from google.cloud import secretmanager

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

def _load_secret_from_secret_manager(secret_reference: str) -> str | None:
    """
    Load a secret from Google Secret Manager if the reference follows the pattern:
    projects/{project_id}/secrets/{secret_id}/versions/{version}
    """
    try:
        if not secret_reference or not secret_reference.startswith("projects/"):
            logger.debug(f"Secret reference doesn't match project pattern: {secret_reference[:20] if secret_reference else 'None'}")
            return None
        
        logger.info(f"Loading secret from Secret Manager: {secret_reference[:50]}...")
        client = secretmanager.SecretManagerServiceClient()
        response = client.access_secret_version(request={"name": secret_reference})
        secret_value = response.payload.data.decode("UTF-8")
        logger.info(f"Successfully loaded secret, length: {len(secret_value)} characters")
        return secret_value
    except Exception as e:
        logger.error(f"Failed to load secret from Secret Manager: {type(e).__name__}: {e}")
        return None

# Load SendGrid API Key
sendgrid_api_key_env = os.getenv("SENDGRID_API_KEY", "").strip()
logger.info(f"SENDGRID_API_KEY env var value: {sendgrid_api_key_env[:50] if sendgrid_api_key_env else 'NOT SET'}")

if sendgrid_api_key_env.startswith("projects/"):
    # It's a Secret Manager reference, load the actual secret
    logger.info("SENDGRID_API_KEY is a Secret Manager reference, loading...")
    SENDGRID_API_KEY = _load_secret_from_secret_manager(sendgrid_api_key_env)
    if not SENDGRID_API_KEY:
        logger.error("Failed to load SENDGRID_API_KEY from Secret Manager")
else:
    # It's a direct API key
    SENDGRID_API_KEY = sendgrid_api_key_env if sendgrid_api_key_env else None
    logger.info(f"SENDGRID_API_KEY is a direct value: {bool(SENDGRID_API_KEY)}")

if not SENDGRID_API_KEY:
    logger.warning("WARNING: SENDGRID_API_KEY not found in environment or Secret Manager")
else:
    logger.info(f"SENDGRID_API_KEY loaded successfully: {SENDGRID_API_KEY[:10]}...")

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
    reader = csv.DictReader(io.StringIO(csv_text), delimiter=';')
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