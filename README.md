# SIMBYP Email Notifications

A Flask-based email notification system that sends alerts for environmental monitoring, including deforestation, built area expansion, and land cover changes. Alerts are triggered by reports stored in Google Cloud Storage and distributed to stakeholders via SendGrid.

## Features

- **Multiple Alert Types**: GFW deforestation alerts, PSA reports, and built area expansion notifications
- **Weekly Digest**: Aggregates alerts from the past week into a summary email
- **Cloud Storage Integration**: Reads alert reports from Google Cloud Storage
- **Dynamic Recipients**: Loads recipient lists from a CSV file stored in GCS
- **HTML Templates**: Professionally formatted email templates for each alert type
- **Cloud-Ready**: Containerized with Docker, deployable on Cloud Run

## Project Structure

```
src/
├── config.py                      # Configuration and environment loading
├── email_service.py               # SendGrid email sending logic
├── gcs_handler.py                 # Google Cloud Storage operations
├── alerts_processor.py            # Alert aggregation and processing
├── utils.py                       # Utility functions
└── templates/                     # HTML email templates
    ├── deforestation_alert.html
    ├── built_area_alert.html
    ├── land_cover_alert.html
    └── weekly_digest.html
main.py                            # Flask application and endpoints
tests/test_email_service.py        # Unit tests
Dockerfile                         # Container configuration
requirements.txt                   # Python dependencies
.env.example                       # Environment variables template
```

## Prerequisites

- Python 3.11+
- Google Cloud Project with:
  - Service account credentials (JSON key file)
  - Storage bucket with alert reports and recipient CSV
- SendGrid account with API key
- Microsoft email account (or any email verified with SendGrid)

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
Nombre,Cargo,Entidad,reporte_gfw,reporte_area_construida,reporte_paramos,weekly_digest,Porqué,Correo,Municipio
John Doe,Analyst,Agency,1,1,0,1,Stakeholder,john@example.com,11001
```

The CSV loader recognizes these columns:
- `Correo`: Email address
- `reporte_gfw`: Include in GFW alerts (1=yes)
- `reporte_area_construida`: Include in built area alerts (1=yes)
- `reporte_paramos`: Include in PSA reports (1=yes)
- `weekly_digest`: Include in weekly digest (1=yes)

### 3. SendGrid Setup

- Sign up at [SendGrid](https://sendgrid.com)
- Create an API Key (Settings → API Keys)
- Add a Single Sender verification (use your Microsoft email account)
- Copy the API key to your `.env` file

### 4. Environment Configuration

Copy `.env.example` to `.env` and fill in values:

```bash
cp .env.example .env
```

Edit `.env`:

```dotenv
# GCP Configuration
GCP_PROJECT_ID=bosques-bogota-416214
RECIPIENTS_CSV_URI=gs://your-bucket/path/to/recipients.csv
GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account-key.json

# SendGrid Configuration
SENDGRID_API_KEY=your-api-key
FROM_EMAIL=alerts@example.com
FROM_NAME=Alert System

# Alert Types (comma-separated fallback recipients)
GFW_RECIPIENTS=user1@example.com,user2@example.com
PSA_RECIPIENTS=user1@example.com
AREA_CONSTRUIDA_RECIPIENTS=user1@example.com
DIGEST_RECIPIENTS=admin@example.com

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

### Send Weekly Digest

```bash
POST /send-weekly-digest
```

Fetches all pending alerts from the last `DAYS_BACK` days, aggregates them, and sends a summary email to digest recipients.

**Response:**
```json
{
  "status": "success",
  "message": "Weekly digest sent successfully",
  "summary": {
    "total_alerts": 5,
    "gfw_count": 2,
    "psa_count": 1,
    "area_construida_count": 2,
    "generated_at": "2026-02-11 10:30:00"
  },
  "recipients": ["admin@example.com"]
}
```

### Test Alerts

```bash
GET /test-alerts
```

Returns a preview of what alerts would be sent (for debugging).

## Deployment

### Docker

```bash
docker build -t simbyp-email-notifications .
docker run -e PORT=8080 --env-file .env simbyp-email-notifications
```

### Google Cloud Run

```bash
gcloud run deploy simbyp-email-notifications \
  --source . \
  --set-env-vars GCP_PROJECT_ID=your-project,SENDGRID_API_KEY=your-key \
  --memory 512Mi \
  --timeout 540
```

## Testing

```bash
pytest tests/
```

## Configuration via CSV

The recipient list is loaded from a CSV file in Google Cloud Storage. The file is read on each app start, so updates to the CSV are picked up automatically. If the CSV is unavailable, the system falls back to the env var recipients.

### Recipient CSV Columns

| Column | Type | Description |
|--------|------|-------------|
| `Correo` | Email | Recipient email address |
| `reporte_gfw` | 0/1 | Include in GFW deforestation alerts |
| `reporte_area_construida` | 0/1 | Include in built area alerts |
| `reporte_paramos` | 0/1 | Include in PSA reports |
| `weekly_digest` | 0/1 | Include in weekly digest |

## Troubleshooting

**Issue**: "SendGrid API key not configured"
- Verify `SENDGRID_API_KEY` is in `.env`

**Issue**: "No recipients configured"
- Check the CSV file exists at `RECIPIENTS_CSV_URI` and is formatted correctly
- Verify GCS service account has read permission

**Issue**: Emails not arriving
- Confirm the sender email is verified in SendGrid
- Check SendGrid Activity Feed for bounce/delivery errors

## Contributing

Daniel Wiesner y Laura Tamayo
