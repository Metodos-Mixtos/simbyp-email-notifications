# SIMBYP Email Notifications

A Flask-based email notification system that sends scheduled environmental alerts including deforestation, built area expansion, and land cover changes. Alerts are triggered on a frequency-based schedule, read from Google Cloud Storage, and delivered via SendGrid.

## Features

- **Frequency-Based Alerts**:
  - Weekly email (every Tuesday): Deforestation (GFW) + Land Cover (PSA) alerts
  - Monthly email (first Friday): Built area expansion alerts
- **Cloud Storage Integration**: Reads alert reports from Google Cloud Storage
- **Deduplication System**: Uses Cloud SQL to prevent duplicate email sends
- **Dynamic Recipients**: Loads recipient lists from a CSV file stored in GCS or environment variables
- **HTML Templates**: Professionally formatted email templates for each alert type
- **Cloud-Ready**: Containerized with Docker, deployable on Cloud Run

## Project Structure

```
src/
├── config.py                      # Configuration and environment loading
├── email_service.py               # SendGrid email sending logic
├── gcs_handler.py                 # Google Cloud Storage operations
├── alerts_processor.py            # Alert aggregation and processing
├── utils.py                       # Database, scheduling, and utility functions
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
```

## Prerequisites

- Python 3.11+
- Google Cloud Project with:
  - Service account credentials (JSON key file)
  - Storage bucket with alert reports and recipient CSV
  - Cloud SQL PostgreSQL instance (for deduplication)
- SendGrid account with API key
- Email account verified with SendGrid

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

# Create Cloud SQL PostgreSQL instance
gcloud sql instances create simbyp-alerts \
  --database-version POSTGRES_15 \
  --tier db-f1-micro \
  --region us-central1
```

Prepare a CSV file in your GCS bucket with recipient data. Example:

```csv
Nombre,Cargo,Entidad,weekly_alerts,monthly_built_area,Correo,Municipio
John Doe,Analyst,Agency,1,1,john@example.com,11001
Jane Smith,Manager,Department,1,0,jane@example.com,11002
```

The CSV loader recognizes these columns:
- `Correo`: Email address (required)
- `weekly_alerts`: Include in weekly deforestation/land cover alerts (1=yes)
- `monthly_built_area`: Include in monthly built area reports (1=yes)

### 3. SendGrid Setup

- Sign up at [SendGrid](https://sendgrid.com)
- Create an API Key (Settings → API Keys)
- Add a Single Sender verification (use your verified email account)
- Copy the API key to your `.env` file

### 4. Environment Configuration

Copy `.env.example` to `.env` and fill in values:

```bash
cp .env.example .env
```

Edit `.env`:

```dotenv
# GCP Configuration
GCP_PROJECT_ID=your-gcp-project-id
RECIPIENTS_CSV_URI=gs://your-bucket/path/to/recipients.csv
GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account-key.json

# SendGrid Configuration
SENDGRID_API_KEY=your-api-key
FROM_EMAIL=alerts@example.com
FROM_NAME=SIMBYP Alertas

# Cloud SQL Configuration (for deduplication)
CLOUD_SQL_INSTANCE=your-project:region:instance-name
CLOUD_SQL_DB=simbyp_alerts
CLOUD_SQL_USER=postgres
CLOUD_SQL_PASSWORD=your-secure-password

# Fallback Recipients (comma-separated, used if CSV unavailable)
WEEKLY_ALERTS_RECIPIENTS=user1@example.com,user2@example.com
MONTHLY_BUILT_AREA_RECIPIENTS=admin@example.com,user3@example.com

# Service Configuration
DAYS_BACK=7
PORT=8080
```

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

Checks if today is the first Friday of the month. If so, fetches built area alerts from the last `DAYS_BACK` days and sends them to monthly built area recipients. Skips if not the first Friday or no alerts found.

**Triggering**: Call via Cloud Scheduler daily at 9 AM UTC (endpoint self-checks for first Friday):
```bash
gcloud scheduler jobs create http send-monthly-built-area \
  --location us-central1 \
  --schedule "0 9 * * *" \
  --uri "https://your-cloud-run-url/send-monthly-built-area" \
  --http-method POST
```

**Response (first Friday with alerts):**
```json
{
  "status": "success",
  "message": "Monthly built area report sent successfully",
  "alerts": 2,
  "recipients": ["admin@example.com"]
}
```

**Response (not first Friday):**
```json
{
  "status": "skipped",
  "message": "Not the first Friday of the month"
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

```bash
docker build -t simbyp-email-notifications .
docker run -e PORT=8080 --env-file .env simbyp-email-notifications
```

### Google Cloud Run

#### For the first time:

1. Ensure Cloud SQL instance is created
2. Create Cloud SQL service account and user
3. Deploy the application:

```bash
gcloud run deploy simbyp-email-notifications \
  --source . \
  --region us-central1 \
  --allow-unauthenticated \
  --set-env-vars \
    GCP_PROJECT_ID=your-project,\
    SENDGRID_API_KEY=your-key,\
    CLOUD_SQL_INSTANCE=your-project:region:instance \
  --memory 512Mi \
  --timeout 540 \
  --service-account your-service-account@your-project.iam.gserviceaccount.com
```

4. Create Cloud Scheduler jobs (see API Endpoints section above)

## Deduplication System

The system uses Cloud SQL PostgreSQL to track sent alerts and prevent duplicates:

- **Table**: `sent_alerts`
- **Fields**: 
  - `id`: Unique alert ID
  - `alert_type`: 'weekly_alerts' or 'monthly_built_area'
  - `report_name`: Name of the report file
  - `recipients_hash`: SHA256 hash of recipient list
  - `recipients_list`: JSON array of recipients
  - `sent_date`: When the alert was sent

Each alert is identified by its type, report name, and recipient list. If the same report is sent to the same group of recipients, the second attempt is skipped.

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

**Issue**: "SendGrid API key not configured"
- Verify `SENDGRID_API_KEY` is in `.env`

**Issue**: "No recipients configured"
- Check the CSV file exists at `RECIPIENTS_CSV_URI` and is formatted correctly
- Verify GCS service account has read permission
- Check environment variables `WEEKLY_ALERTS_RECIPIENTS` or `MONTHLY_BUILT_AREA_RECIPIENTS`

**Issue**: Emails not arriving
- Confirm the sender email is verified in SendGrid
- Check SendGrid Activity Feed for bounce/delivery errors

**Issue**: Cloud SQL connection errors
- Verify Cloud SQL instance exists and is running
- Check database credentials in `.env`
- Ensure service account has Cloud SQL Client role

**Issue**: Duplicate emails being sent
- Check `sent_alerts` table in Cloud SQL
- Verify recipients list hasn't changed between sends

## Contributing

Daniel Wiesner y Laura Tamayo

