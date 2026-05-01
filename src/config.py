import os
import logging
import csv
import io
from dotenv import load_dotenv  # ← ADD THIS
from google.cloud import storage
from google.cloud import secretmanager

# Load .env file FIRST (before any other config loading)
# This makes Tier 2 of the 3-tier pattern work
load_dotenv()

logger = logging.getLogger(__name__)

# ============================================================================
# HELPER FUNCTION: 3-TIER SECRETS LOADING
# ============================================================================
def _load_from_secret_manager(secret_reference: str) -> str | None:
    """
    Load a secret from Google Secret Manager.
    Reference format: projects/{project_id}/secrets/{secret_id}/versions/{version}
    """
    try:
        if not secret_reference or not secret_reference.startswith("projects/"):
            logger.debug(f"Invalid secret reference format: {secret_reference[:50] if secret_reference else 'None'}")
            return None
        
        logger.debug(f"Accessing Secret Manager: {secret_reference[:60]}...")
        client = secretmanager.SecretManagerServiceClient()
        response = client.access_secret_version(request={"name": secret_reference})
        secret_value = response.payload.data.decode("UTF-8").strip()
        logger.debug(f"Successfully retrieved secret from Secret Manager")
        return secret_value
    except Exception as e:
        logger.error(f"Failed to load from Secret Manager: {type(e).__name__}: {e}")
        return None

def _load_secret_tiered(secret_name: str, default: str = "") -> str:
    """
    Load a secret following 3-tier practice:
    1. Direct environment variable (os.environ - set at runtime)
    2. From .env file (loaded by python-dotenv at startup)
    3. From Google Secret Manager (if value is a projects/... reference)
    4. From Cloud Run secret mounts (--set-secrets)
    
    Args:
        secret_name: The environment variable name to load
        default: Default value if not found anywhere
    
    Returns:
        The secret value or default
    """
    logger.info(f"=== Loading {secret_name} ===")
    
    # Tier 1 & 2: Check environment (includes .env loaded values)
    value = os.getenv(secret_name, "").strip()
    if value:
        logger.info(f"✓ Found {secret_name} in Tier 1/2 (environment or .env)")
        # If it's a Secret Manager reference, load it (Tier 3)
        if value.startswith("projects/"):
            logger.info(f"  → Value is Secret Manager reference, loading from Tier 3...")
            loaded = _load_from_secret_manager(value)
            if loaded:
                logger.info(f"  ✓ Successfully loaded {secret_name} from Secret Manager")
                return loaded
            else:
                logger.error(f"  ✗ Failed to load {secret_name} from Secret Manager")
                return default
        else:
            logger.info(f"  ✓ {secret_name} is a direct value")
            return value
    
    # Tier 3: If not found in env/env file, try Google Secret Manager with auto-constructed path
    logger.info(f"Tier 1/2 - {secret_name} not found or empty, trying Tier 3 (GSM)...")
    gsm_path = f"projects/{GCP_PROJECT_ID}/secrets/{secret_name}/versions/latest"
    logger.info(f"Trying GSM path: {gsm_path}")
    loaded = _load_from_secret_manager(gsm_path)
    if loaded:
        logger.info(f"✓ Successfully loaded {secret_name} from GSM (Tier 3)")
        return loaded
    
    # Tier 4: Try Cloud Run secret file mount (--set-secrets AZURE_CLIENT_ID=... mounts as files)
    mount_path = f"/var/run/secrets/cloud.google.com/{secret_name}"
    if os.path.exists(mount_path):
        logger.info(f"✓ Found {secret_name} in Cloud Run secret mount: {mount_path}")
        try:
            with open(mount_path, 'r') as f:
                value = f.read().strip()
                if value:
                    logger.info(f"  ✓ Successfully loaded {secret_name} from Cloud Run secret mount")
                    return value
        except Exception as e:
            logger.error(f"  ✗ Failed to read Cloud Run secret file: {e}")
    
    # Try alternative Cloud Run mount path
    alt_mount_path = f"/run/secrets/{secret_name}"
    if os.path.exists(alt_mount_path):
        logger.info(f"✓ Found {secret_name} in alternative mount: {alt_mount_path}")
        try:
            with open(alt_mount_path, 'r') as f:
                value = f.read().strip()
                if value:
                    logger.info(f"  ✓ Successfully loaded {secret_name} from alternative mount")
                    return value
        except Exception as e:
            logger.error(f"  ✗ Failed to read alternative mount: {e}")
    
    logger.warning(f"✗ {secret_name} not found in any tier")
    return default

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
# MICROSOFT GRAPH CREDENTIALS (using 3-tier loading)
# ============================================================================
AZURE_CLIENT_ID = _load_secret_tiered('AZURE_CLIENT_ID')
AZURE_TENANT_ID = _load_secret_tiered('AZURE_TENANT_ID')
AZURE_CLIENT_SECRET = _load_secret_tiered('AZURE_CLIENT_SECRET')

if AZURE_CLIENT_ID and AZURE_TENANT_ID and AZURE_CLIENT_SECRET:
    logger.info("✓ Azure AD credentials loaded successfully")
else:
    logger.error(f"✗ Missing Azure AD credentials: client_id={bool(AZURE_CLIENT_ID)}, tenant_id={bool(AZURE_TENANT_ID)}, client_secret={bool(AZURE_CLIENT_SECRET)}")

# ============================================================================
# HELPER FUNCTIONS FOR CSV & RECIPIENTS
# ============================================================================
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