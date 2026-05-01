# SIMBYP Email Notifications

A Flask-based email notification system that sends scheduled environmental alerts including deforestation, built area expansion, and land cover changes. Alerts are triggered on a frequency-based schedule, read from Google Cloud Storage, and delivered via Microsoft Graph API (Office 365/Microsoft 365).

## Features

- **Frequency-Based Alerts**:
  - Weekly email (every Tuesday): Deforestation (GFW) + Land Cover (PSA) alerts
  - Monthly email (first Friday): Built area expansion alerts
- **Cloud Storage Integration**: Reads alert reports from Google Cloud Storage
- **Dynamic Recipients**: Loads recipient lists from a CSV file stored in GCS or environment variables
- **HTML Templates**: Professionally formatted email templates for each alert type
- **Cloud-Ready**: Containerized with Docker, deployable on Cloud Run
- **Microsoft 365 Native**: Uses Microsoft Graph API for native Office 365 integration
- **Simple & Lightweight**: No database dependency, lightweight deployment

## Project Structure

```
src/
├── config.py                      # Configuration and environment loading
├── email_service.py               # Microsoft Graph email sending logic
├── gcs_handler.py                 # Google Cloud Storage operations
├── alerts_processor.py            # Alert aggregation and processing
├── utils.py                       # Scheduling and utility functions
└── templates/                     # HTML email templates
    ├── built_area_alert.html      # Monthly built area report
    └── weekly_alerts.html         # Weekly deforestation + land cover alerts
main.py                            # Flask application and endpoints
tests/
├── test_email_service.py          # Email service tests
├── test_utils.py                  # Utility function tests
Dockerfile                         # Container configuration
requirements.txt                   # Python dependencies
.env.example                       # Environment variables template
AZURE_SETUP.md                     # Azure AD app registration guide
```

## Prerequisites

- Python 3.11+
- Google Cloud Project with:
  - Service account credentials (JSON key file)
  - Storage bucket with alert reports and recipient CSV
- Microsoft 365 / Office 365 tenant with:
  - Azure AD admin access for app registration
  - Email account `simbyp@sdp.gov.co` in the tenant

## Setup Instructions

### 1. Clone and Install

```bash
git clone <repository-url>
cd simbyp-email-notifications
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Google Cloud Setup

```bash
# Create a service account and download the JSON key
export GOOGLE_APPLICATION_CREDENTIALS="path/to/service-account-key.json"
```

Prepare a CSV file in your GCS bucket with recipient data. Example:

```csv
Nombre,Cargo,Entidad,weekly_alerts,monthly_built_area,Correo,Municipio
John Doe,Analyst,Agency,1,1,john@example.com,11001
Jane Smith,Manager,Department,1,0,jane@example.com,11002
```

En este enlace está la lista de distribución: 
https://docs.google.com/spreadsheets/d/1NBNmaZpirgpqpWILlv1tTC1xUlpHnwaReyJtwaKxhQ0/edit?usp=sharing

La ubicación en GCS es: 
gs://material-estatico-sdp/SIMBYP_DATA/listas_distribucion/lista_circulacion_reportes - test.csv


The CSV loader recognizes these columns:
- `Correo`: Email address (required)
- `weekly_alerts`: Include in weekly deforestation/land cover alerts (1=yes)
- `monthly_built_area`: Include in monthly built area reports (1=yes)

### 3. Azure AD Setup

**See [AZURE_SETUP.md](AZURE_SETUP.md) for complete Azure AD app registration instructions.**

Quick summary:
1. Register an app in Azure AD
2. Create a client secret
3. Grant `Mail.Send` permission in Microsoft Graph
4. Save your credentials:
   - Application (client) ID
   - Directory (tenant) ID
   - Client Secret

### 4. Environment Configuration

The application uses **defaults from `src/config.py`** for non-secret configuration and follows a **3-tier secrets loading pattern**:

**Tier 1:** Direct environment variables (runtime)  
**Tier 2:** Variables from `.env` file (local dev)  
**Tier 3:** Google Secret Manager (cloud)  
**Tier 4:** Cloud Run secret mounts (fallback)

```bash
cp .env.example .env
```

Edit `.env` - required for local development:

```dotenv
# REQUIRED: Azure AD Credentials (keep secure!)
AZURE_CLIENT_ID=your-client-id
AZURE_TENANT_ID=your-tenant-id
AZURE_CLIENT_SECRET=your-client-secret

# OPTIONAL: Google service account for local dev only
GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account-key.json

# OPTIONAL: Override defaults if needed (most are defined in src/config.py)
# GCP_PROJECT_ID=your-project
# FROM_EMAIL=custom@example.com
# RECIPIENTS_CSV_URI=gs://custom-bucket/recipients.csv
```

**Application defaults** (defined in `src/config.py`):
- `GCP_PROJECT_ID`: bosques-bogota-416214
- `FROM_EMAIL`: simbyp@sdp.gov.co
- `FROM_NAME`: SIMBYP Alertas
- `RECIPIENTS_CSV_URI`: gs://material-estatico-sdp/...
- `DAYS_BACK`: 20
- `PORT`: 8080

### 5. Run Locally

```bash
python main.py
```

The app runs on `http://localhost:8080`

## API Endpoints

### Health Check

```bash
GET /
```

Returns service status.

### Send Weekly Alerts

```bash
POST /send-weekly-alerts
```

Fetches deforestation (GFW) and land cover (PSA) alerts from the last `DAYS_BACK` days, and sends them to weekly alert recipients. Skips if no alerts are found.

**Triggering**: Call via Cloud Scheduler every Tuesday at 9 AM UTC:
```bash
gcloud scheduler jobs create http send-weekly-alerts \
  --location us-central1 \
  --schedule "0 9 * * TUE" \
  --uri "https://your-cloud-run-url/send-weekly-alerts" \
  --http-method POST
```

**Response (with alerts):**
```json
{
  "status": "success",
  "message": "Weekly alerts sent successfully",
  "alerts": 3,
  "recipients": ["user1@example.com", "user2@example.com"]
}
```

**Response (no alerts):**
```json
{
  "status": "skipped",
  "message": "No alerts found for this week",
  "alerts": 0
}
```

### Send Monthly Built Area Report

```bash
POST /send-monthly-built-area
```

Fetches built area alerts from the last `DAYS_BACK` days and sends them to monthly built area recipients. Skips if no alerts found.

**Triggering**: Call via Cloud Scheduler only on the first Friday of each month at 9 AM UTC using a cron expression:
```bash
gcloud scheduler jobs create http send-monthly-built-area \
  --location us-central1 \
  --schedule "0 9 1-7 * FRI" \
  --uri "https://your-cloud-run-url/send-monthly-built-area" \
  --http-method POST
```

The cron expression `0 9 1-7 * FRI` ensures the job runs only on Fridays that fall within the first 7 days of the month, eliminating unnecessary daily wake-ups.

**Response (with alerts):**
```json
{
  "status": "success",
  "message": "Monthly built area report sent successfully",
  "alerts": 2,
  "recipients": ["admin@example.com"]
}
```

**Response (no alerts):**
```json
{
  "status": "skipped",
  "message": "No built area alerts found",
  "alerts": 0
}
```

### Test Alerts

```bash
GET /test-alerts
```

Returns a preview of what alerts would be sent (for debugging/monitoring).

**Response:**
```json
{
  "weekly_alerts": {
    "deforestation": [
      {
        "title": "Alertas GFW - I Trimestre 2026",
        "updated": "2026-02-11T10:30:00"
      }
    ],
    "land_cover": []
  },
  "monthly_built_area": {
    "alerts": [
      {
        "title": "Alerta de Área Construida",
        "updated": "2026-02-06T15:45:00"
      }
    ],
    "is_first_friday": true
  }
}
```

## Deployment

### Docker

**Build locally** (uses your current architecture):
```bash
docker build -t simbyp-email-notifications .

# Run with .env file (local development)
docker run -e PORT=8080 --env-file .env simbyp-email-notifications

# Or pass credentials directly
docker run -e PORT=8080 \
  -e AZURE_CLIENT_ID=your-id \
  -e AZURE_TENANT_ID=your-tenant \
  -e AZURE_CLIENT_SECRET=your-secret \
  simbyp-email-notifications
```

**Build for GCP Cloud Run** (Linux amd64, recommended when on macOS):
```bash
# Using docker buildx for cross-platform builds (recommended)
docker buildx build --platform linux/amd64 -t simbyp-email-notifications:latest .

# Or push directly to GCP Container Registry
docker buildx build --platform linux/amd64 \
  -t gcr.io/bosques-bogota-416214/simbyp-email-notifications:latest \
  --push .
```

### Google Cloud Run

Azure AD credentials are managed in GCP Secret Manager. The deployment process:

**1. Store credentials in GCP Secret Manager (one-time setup):**
```bash
gcloud secrets create AZURE_CLIENT_ID --replication-policy="automatic" --data-file=- <<< "YOUR_CLIENT_ID"
gcloud secrets create AZURE_TENANT_ID --replication-policy="automatic" --data-file=- <<< "YOUR_TENANT_ID"
gcloud secrets create AZURE_CLIENT_SECRET --replication-policy="automatic" --data-file=- <<< "YOUR_CLIENT_SECRET"
```

**2. Grant service account access to secrets (one-time setup):**
```bash
PROJECT_ID="bosques-bogota-416214"
SERVICE_ACCOUNT="sa-bosques-app@${PROJECT_ID}.iam.gserviceaccount.com"

for secret in AZURE_CLIENT_ID AZURE_TENANT_ID AZURE_CLIENT_SECRET; do
  gcloud secrets add-iam-policy-binding "$secret" \
    --member="serviceAccount:${SERVICE_ACCOUNT}" \
    --role="roles/secretmanager.secretAccessor"
done

gcloud projects add-iam-policy-binding ${PROJECT_ID} \
  --member="serviceAccount:${SERVICE_ACCOUNT}" \
  --role="roles/storage.objectViewer"
```

**3. Deploy with secrets (Option A - Environment Variables with Secret Manager references):**

```bash
gcloud run deploy simbyp-email-notifications \
  --source . \
  --region us-central1 \
  --allow-unauthenticated \
  --memory=256Mi \
  --timeout=300 \
  --set-env-vars \
    AZURE_CLIENT_ID=projects/548822075986/secrets/AZURE_CLIENT_ID/versions/latest,\
    AZURE_TENANT_ID=projects/548822075986/secrets/AZURE_TENANT_ID/versions/latest,\
    AZURE_CLIENT_SECRET=projects/548822075986/secrets/AZURE_CLIENT_SECRET/versions/latest \
  --service-account="sa-bosques-app@bosques-bogota-416214.iam.gserviceaccount.com" \
  --project=bosques-bogota-416214
```

**3b. Deploy with secrets (Option B - Cloud Run Secret Mounts - recommended):**

```bash
gcloud run deploy simbyp-email-notifications \
  --source . \
  --region us-central1 \
  --allow-unauthenticated \
  --memory=256Mi \
  --timeout=300 \
  --set-secrets \
    AZURE_CLIENT_ID=AZURE_CLIENT_ID:latest,\
    AZURE_TENANT_ID=AZURE_TENANT_ID:latest,\
    AZURE_CLIENT_SECRET=AZURE_CLIENT_SECRET:latest \
  --service-account="sa-bosques-app@bosques-bogota-416214.iam.gserviceaccount.com" \
  --project=bosques-bogota-416214
```

**3-Tier Secrets Loading**: The code automatically detects where secrets come from:
- **Tier 1**: Environment variables (direct values)
- **Tier 2**: .env file (local development only)
- **Tier 3**: Google Secret Manager (if value is `projects/.../secrets/.../versions/...`)
- **Tier 4**: Cloud Run secret mounts (if using `--set-secrets`)

✅ **Status**: System tested and operational. Emails successfully sent to recipients via Microsoft 365.

For complete deployment instructions including troubleshooting, see [GCP_DEPLOYMENT.md](GCP_DEPLOYMENT.md).

## Testing

```bash
pytest tests/ -v
```

Run specific test file:
```bash
pytest tests/test_email_service.py -v
pytest tests/test_utils.py -v
```

## Configuration via CSV

The recipient list is loaded from a CSV file in Google Cloud Storage. The file is read on each app start, so updates to the CSV are picked up automatically. If the CSV is unavailable, the system falls back to the env var recipients.

### Recipient CSV Columns

| Column | Type | Description |
|--------|------|-------------|
| `Correo` | Email | Recipient email address (required) |
| `weekly_alerts` | 0/1 | Include in weekly deforestation/land cover alerts (1=yes) |
| `monthly_built_area` | 0/1 | Include in monthly built area reports (1=yes) |

## Troubleshooting

**Issue**: "Missing Azure AD credentials"
- Verify `AZURE_CLIENT_ID`, `AZURE_TENANT_ID`, `AZURE_CLIENT_SECRET` are set
- Check in `.env` (local) or via `gcloud secrets list` (Cloud Run)
- Follow [AZURE_SETUP.md](AZURE_SETUP.md) to ensure app is registered correctly

**Issue**: "Authentication_RequestDenied" or "Insufficient privileges"
- Verify app has `Mail.Send` permission in Microsoft Graph
- Check that admin consent was granted (see AZURE_SETUP.md step 3.7)
- Service account needs permissions to send emails on behalf of `simbyp@sdp.gov.co`

**Issue**: "No recipients configured"
- Check the CSV file exists at `RECIPIENTS_CSV_URI` (default: gs://material-estatico-sdp/...) and is formatted correctly
- Verify GCS service account has read permission
- Check environment variables `WEEKLY_ALERTS_RECIPIENTS` or `MONTHLY_BUILT_AREA_RECIPIENTS` if overriding CSV

**Issue**: Emails not arriving
- Check Azure AD audit logs for send failures
- Verify `simbyp@sdp.gov.co` email exists in Microsoft 365
- Confirm recipient email addresses are valid

**Issue**: GCS connection errors
- Verify service account has Storage Object Viewer role on the bucket
- Check `RECIPIENTS_CSV_URI` is correct (uses default from `src/config.py` if not overridden)
- For local dev: set `GOOGLE_APPLICATION_CREDENTIALS` in `.env`

**Issue**: Different configuration per environment
- Override specific values via environment variables (Tier 1)
- Use `.env` for local development (Tier 2)
- Use Google Secret Manager for cloud deployments (Tier 3)
- Defaults from `src/config.py` are used for anything not explicitly set

## Deployment Status

✅ **Production Ready**: The system is deployed and tested on GCP Cloud Run
- Email sending verified with Microsoft Graph API
- Recipients loaded from GCS CSV (with BCC to hide recipient list)
- Microsoft 365 integration tested and confirmed
- Alerts loading from GCS buckets confirmed
- 3-tier secrets loading pattern implemented

## Notes

- **Configuration Strategy**: Non-secret defaults are defined in `src/config.py` for simplicity and clarity. Secrets follow a 3-tier loading pattern: direct environment → .env file → Google Secret Manager. The code automatically detects where each secret comes from and loads it accordingly.
- **Email Delivery**: Uses Microsoft Graph API with service account authentication (application permissions). Emails are sent on behalf of `simbyp@sdp.gov.co` using the organization's Microsoft 365 tenant.
- **BCC Privacy**: Recipients are added to BCC to hide them from each other while preserving email delivery traceability.
- **Email Duplicates**: The system no longer prevents duplicate emails. If the same alert is triggered multiple times, it may be sent multiple times to the recipients. This is intentional for simplicity.
- **Simple & Lightweight**: No database dependency means faster deployments and lower operational overhead.
- **Stateless**: Each service invocation is independent; no state is maintained between calls.

## Contributing

Daniel Wiesner y Laura Tamayo

