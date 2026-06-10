# SIMBYP Email Notifications

A Flask-based email notification system that sends scheduled environmental alerts including deforestation, built area expansion, and land cover changes. Alerts are triggered on a frequency-based schedule, read from Google Cloud Storage, and delivered via Microsoft Graph API (Office 365/Microsoft 365).

## Features

- **Frequency-Based Alerts**:
  - Weekly email (every Tuesday): Deforestation (GFW) + Land Cover (PSA) alerts
  - Monthly email (first Friday): Built area expansion alerts
- **Cloud Storage Integration**: Reads alert reports from Google Cloud Storage
- **Database-Driven Recipient Management**: PostgreSQL for dynamic user management with subscriptions
- **Admin User Management**: Browser-based interface for managing email recipients and subscriptions
- **Database Support**: PostgreSQL integration with ORM models and repository pattern
- **HTML Templates**: Professionally formatted email templates for each alert type
- **Cloud-Ready**: Containerized with Docker, deployable on Cloud Run
- **Microsoft 365 Native**: Uses Microsoft Graph API for native Office 365 integration
- **Comprehensive Audit Logging**: Tracks all user and subscription changes

## Project Structure

```
src/
├── config.py                      # Configuration and environment loading (3-tier secrets)
├── database.py                    # SQLAlchemy engine and session management
├── email_service.py               # Microsoft Graph email sending logic
├── gcs_handler.py                 # Google Cloud Storage operations
├── alerts_processor.py            # Alert aggregation and processing
├── utils.py                       # Scheduling and utility functions
├── models/                        # SQLAlchemy ORM models
│   ├── user.py                    # User model
│   ├── subscription.py            # Subscription model
│   ├── audit.py                   # Subscription audit model
│   ├── report.py                  # Report model (for tracking)
│   ├── alert_statistic.py         # Alert statistics model
│   └── report_recipient.py        # Report recipient tracking
├── repositories/                  # Data access layer
│   ├── user_repository.py         # User CRUD operations
│   ├── subscription_repository.py # Subscription management
│   └── report_repository.py       # Report operations
├── static/
│   └── js/
│       └── admin.js               # Admin UI JavaScript
└── templates/                     # HTML email templates
    ├── built_area_alert.html      # Monthly built area report
    ├── weekly_alerts.html         # Weekly deforestation + land cover alerts
    └── weekly_report.html         # Weekly report template
main.py                            # Flask application and endpoints
migrations/
├── 001_initial_schema.sql         # Users, subscriptions, audit tables
└── 002_reports_tracking.sql       # Report tracking tables
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
- **PostgreSQL 15+** (required for recipient management)
- Google Cloud Project with:
  - Service account credentials (JSON key file)
  - Storage bucket with alert reports
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

### 2. Database Setup

**PostgreSQL is required.** See [docs/CLOUD_SQL_SETUP.md](docs/CLOUD_SQL_SETUP.md) for detailed setup instructions.

Quick setup for local development:

```bash
# Install PostgreSQL (example for macOS)
brew install postgresql

# Start PostgreSQL
brew services start postgresql

# Create database
createdb simbyp

# Run migrations
psql simbyp < migrations/001_initial_schema.sql
psql simbyp < migrations/002_reports_tracking.sql
```

### 3. Google Cloud Setup

```bash
# Create a service account and download the JSON key
export GOOGLE_APPLICATION_CREDENTIALS="path/to/service-account-key.json"
```

### 4. Azure AD Setup

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

### 4. Environment Configuration

The application uses **defaults from `src/config.py`** for non-secret configuration and follows a **4-tier secrets loading pattern**:

**Tier 1:** Direct environment variables (highest priority - runtime)  
**Tier 2:** Variables from `.env` file (local dev)  
**Tier 3:** Google Secret Manager (`projects/{project}/secrets/{name}/versions/latest`)  
**Tier 4:** Cloud Run secret mounts (`/var/run/secrets/...` or `/run/secrets/...`)

The system automatically detects where secrets come from and loads them accordingly.

```bash
cp .env.example .env
```

Edit `.env` - required for local development:

```dotenv
# REQUIRED: Azure AD Credentials (keep secure!)
AZURE_CLIENT_ID=your-client-id
AZURE_TENANT_ID=your-tenant-id
AZURE_CLIENT_SECRET=your-client-secret

# REQUIRED: Database connection
DATABASE_URL=postgresql://simbyp_app:password@/simbyp_db?host=/cloudsql/bosques-bogota-416214:us-central1:simbyp-users-db
REMOTE_DB_ONLY=true
EXPECTED_CLOUD_SQL_INSTANCE=bosques-bogota-416214:us-central1:simbyp-users-db

# OPTIONAL: Google service account for local dev only
GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account-key.json

# OPTIONAL: Override defaults if needed (most are defined in src/config.py)
# GCP_PROJECT_ID=your-project
# FROM_EMAIL=custom@example.com
```

For local development with a remote-only database, run Cloud SQL Auth Proxy using the Unix socket path that matches `DATABASE_URL`:

```bash
cloud-sql-proxy --unix-socket /cloudsql \
  bosques-bogota-416214:us-central1:simbyp-users-db
```

**Application defaults** (defined in `src/config.py`):
- `GCP_PROJECT_ID`: bosques-bogota-416214
- `FROM_EMAIL`: simbyp@sdp.gov.co
- `FROM_NAME`: SIMBYP Alertas
- `DAYS_BACK`: 20
- `PORT`: 8080

### 5. Run Locally

```bash
python main.py
```

The app runs on `http://localhost:8080`

## Admin User Management Interface

The system includes a fully-functional browser-based admin interface for managing email recipients and subscriptions.

### Accessing the Admin Interface

1. **Set up the database** (see setup instructions above)

2. **Run the database migrations** to create the required tables:
   ```bash
   # Migration 001: Core tables (users, subscriptions, audit)
   psql -d your_database -f migrations/001_initial_schema.sql
   
   # Migration 002: Report tracking (optional)
   psql -d your_database -f migrations/002_reports_tracking.sql
   ```

3. **Start the application** and navigate to:
   ```
   http://localhost:8080/admin
   ```

### Features

The admin interface provides a complete user management system with:

- **User Management**:
  - Create new email recipients with details (email, name, department, municipality)
  - Edit existing users
  - Delete users (cascades to subscriptions and audit logs)
  - Search/filter users by email or name
  - Paginated table view (100 users per page)

- **Subscription Management**:
  - **Weekly Alerts**: Subscribe users to weekly deforestation and land cover alerts
  - **Monthly Built Area**: Subscribe users to monthly built area expansion reports
  - Toggle subscriptions on/off per user
  - Visual badges showing active subscriptions
  - Audit trail tracks all subscription changes

- **Real-time Updates**:
  - All changes immediately applied to the database
  - Toast notifications for success/error feedback
  - Automatic table refresh after operations
  - Responsive Bootstrap 5 UI

### User Fields

| Field | Required | Description |
|-------|----------|-------------|
| Email | Yes | User's email address (must be unique) |
| Name | No | User's full name |
| Department | No | Department or organization |
| Municipality Code | No | Colombian municipality DIVIPOLA code (e.g., 11001 for Bogotá) |
| Subscriptions | No | Weekly Alerts and/or Monthly Built Area |

### Database vs CSV Mode

The system supports two recipient management modes:

**Database Mode** (recommended for production):
- Enable with `DB_ENABLED=true`
- Recipients stored in PostgreSQL
- Admin interface available at `/admin`
- Supports audit logging and subscription management
- Provides user search and filtering
- REST API for programmatic access

**CSV Mode** (legacy):
- Reads recipients from GCS CSV file (default: gs://material-estatico-sdp/...)
- Simple setup, no database required
- No admin interface
- Limited to email and basic flags (weekly_alerts, monthly_built_area)
- Requires CSV columns: `Correo`, `weekly_alerts`, `monthly_built_area`

To use database mode, ensure migrations are applied and `DATABASE_URL` is configured.

## API Endpoints

### Health Check

```bash
GET /
```

Returns service status and database health (if enabled).

**Response:**
```json
{
  "status": "healthy",
  "service": "simbyp-email-notifications",
  "database": {
    "enabled": true,
    "status": "healthy",
    "message": "Database connection successful"
  }
}
```

### Database Health Check

```bash
GET /health/db
```

Dedicated database health check endpoint.

**Response (healthy):**
```json
{
  "status": "healthy",
  "message": "Database connection successful"
}
```

**Response (disabled):**
```json
{
  "status": "disabled",
  "message": "Database is not enabled (DB_ENABLED=false)"
}
```

### Send Weekly Alerts

```bash
POST /send-weekly-alerts
```

Fetches the latest weekly alerts report (deforestation + land cover) from GCS and sends to weekly alert recipients. Skips if no report found.

**Triggering**: Call via Cloud Scheduler every Tuesday at 9 AM UTC:
```bash
gcloud scheduler jobs create http send-weekly-alerts \
  --location us-central1 \
  --schedule "0 9 * * TUE" \
  --uri "https://your-cloud-run-url/send-weekly-alerts" \
  --http-method POST
```

**Response (with report):**
```json
{
  "status": "success",
  "message": "Weekly report sent successfully",
  "report": "Alertas GFW - Reporte Semanal",
  "recipients": ["user1@example.com", "user2@example.com"]
}
```

**Response (no report):**
```json
{
  "status": "skipped",
  "message": "No weekly report found",
  "report": null
}
```

### Send Monthly Built Area Report

```bash
POST /send-monthly-built-area
```

Fetches built area alerts from GCS and sends to monthly built area recipients. Only sends on the first Friday of each month. Skips if no alerts found.

**Triggering**: Call via Cloud Scheduler on the first Friday of each month at 9 AM UTC:
```bash
gcloud scheduler jobs create http send-monthly-built-area \
  --location us-central1 \
  --schedule "0 9 1-7 * FRI" \
  --uri "https://your-cloud-run-url/send-monthly-built-area" \
  --http-method POST
```

The cron expression `0 9 1-7 * FRI` ensures the job runs only on Fridays within the first 7 days of the month.

**Response (with alerts):**
```json
{
  "status": "success",
  "message": "Monthly built area report sent successfully",
  "alerts": 1,
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
  "weekly_report": {
    "title": "Alertas GFW - Reporte Semanal",
    "url": "https://gcs-url/report.pdf",
    "start_date": "2026-02-01",
    "end_date": "2026-02-07",
    "updated": "2026-02-11T10:30:00"
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

### Admin User Management API

When database mode is enabled (`DB_ENABLED=true`), the following API endpoints are available:

#### List Users
```bash
GET /api/users?offset=0&limit=100
```

Returns paginated list of all users with their subscriptions.

**Response:**
```json
{
  "success": true,
  "data": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "email": "user@example.com",
      "name": "John Doe",
      "department": "Planning",
      "municipality_code": "11001",
      "subscriptions": ["weekly_alerts", "monthly_built_area"],
      "created_at": "2026-01-15T10:30:00",
      "updated_at": "2026-02-01T14:20:00"
    }
  ],
  "total": 45,
  "offset": 0,
  "limit": 100
}
```

#### Create User
```bash
POST /api/users
Content-Type: application/json

{
  "email": "user@example.com",
  "name": "John Doe",
  "department": "Planning",
  "municipality_code": "11001",
  "subscriptions": ["weekly_alerts", "monthly_built_area"]
}
```

**Response (201 Created):**
```json
{
  "success": true,
  "data": {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "email": "user@example.com",
    "subscriptions": ["weekly_alerts", "monthly_built_area"]
  },
  "message": "User created successfully"
}
```

#### Get User
```bash
GET /api/users/{user_id}
```

Returns details for a specific user.

#### Update User
```bash
PUT /api/users/{user_id}
Content-Type: application/json

{
  "email": "newemail@example.com",
  "name": "Jane Doe",
  "subscriptions": ["weekly_alerts"]
}
```

#### Delete User
```bash
DELETE /api/users/{user_id}
```

Deletes user and all associated subscriptions and audit logs.

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

### Google Cloud Run with Secret Manager

Azure AD credentials are managed securely in GCP Secret Manager. The deployment process supports both secret references and direct secret mounts.

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

**3a. Deploy with Secret Manager references (Option A - Environment Variables):**

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

**3b. Deploy with Cloud Run Secret Mounts (Option B - Recommended):**

Cloud Run secret mounts automatically load secrets into files, eliminating the need for the application to load them:

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

### Secrets Loading Priority (4-Tier Pattern)

The application automatically detects where secrets come from and loads them in this order:

1. **Environment variables** (direct values, highest priority)
2. **.env file** (local development only)
3. **Google Secret Manager** (if value is `projects/.../secrets/.../versions/...`)
4. **Cloud Run secret mounts** (`/var/run/secrets/...` or `/run/secrets/...`, lowest priority)

**Example flow:**
- If `AZURE_CLIENT_SECRET` is set as an env var, it uses that directly
- If not, it checks `.env` file
- If `.env` contains a Secret Manager reference (`projects/.../secrets/...`), it fetches from Secret Manager
- If Cloud Run secret mount exists, it reads from the file mount

This allows the same application code to work across local development, CI/CD pipelines, and production Cloud Run deployments without any changes.

### Cloud SQL Setup (Optional)

For database mode (admin interface), set up Cloud SQL:

```bash
# Create PostgreSQL instance
gcloud sql instances create simbyp-db \
  --database-version=POSTGRES_15 \
  --region=us-central1 \
  --tier=db-f1-micro

# Create database
gcloud sql databases create simbyp \
  --instance=simbyp-db

# Create user and password
gcloud sql users create simbyp_app --instance=simbyp-db --password

# Deploy migrations
gcloud sql connect simbyp-db --user=simbyp_app
# Then run migrations in psql
```

For complete Cloud SQL setup instructions, see [docs/CLOUD_SQL_SETUP.md](docs/CLOUD_SQL_SETUP.md).

**3c. Deploy with Database Mode (Optional):**

If using Cloud SQL:

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
    AZURE_CLIENT_SECRET=AZURE_CLIENT_SECRET:latest,\
    DATABASE_URL=DATABASE_URL:latest \
  --set-env-vars DB_ENABLED=true \
  --service-account="sa-bosques-app@bosques-bogota-416214.iam.gserviceaccount.com" \
  --project=bosques-bogota-416214
```

✅ **Status**: System tested and operational. Emails successfully sent to recipients via Microsoft 365.

For complete deployment instructions including troubleshooting, see [GCP_DEPLOYMENT.md](GCP_DEPLOYMENT.md).

## Testing

```bash
# Run all tests
pytest tests/ -v

# Run specific test file
pytest tests/test_email_service.py -v
pytest tests/test_utils.py -v

# Run with coverage
pytest tests/ -v --cov=src
```

## Configuration via CSV (Legacy Mode)

When database mode is disabled (`DB_ENABLED=false`), the recipient list is loaded from a CSV file in Google Cloud Storage. The file is read on each app start, so updates to the CSV are picked up automatically. If the CSV is unavailable, the system falls back to the env var recipients.

### Recipient CSV Columns

| Column | Type | Description |
|--------|------|-------------|
| `Correo` | Email | Recipient email address (required) |
| `weekly_alerts` | 0/1 | Include in weekly deforestation/land cover alerts (1=yes) |
| `monthly_built_area` | 0/1 | Include in monthly built area reports (1=yes) |

**Example CSV:**
```csv
Nombre,Cargo,Entidad,weekly_alerts,monthly_built_area,Correo,Municipio
John Doe,Analyst,Agency,1,1,john@example.com,11001
Jane Smith,Manager,Department,1,0,jane@example.com,11002
```

The CSV loader is flexible and only requires the `Correo` column. Other columns are optional and informational.

## Troubleshooting

### Database Issues

**Issue**: "Database not initialized" error
- Ensure `DB_ENABLED=true` and `DATABASE_URL` is set
- Check that migrations have been run: `psql -d your_database -f migrations/001_initial_schema.sql`
- Verify database user has proper permissions

**Issue**: Database connection timeout
- Check network connectivity to PostgreSQL (firewall rules, Cloud SQL proxy, etc.)
- Verify `DATABASE_URL` format is correct
- For Cloud Run: ensure service account has Cloud SQL Client role
- Check connection pool settings in `src/database.py` if under high load

**Issue**: "Admin interface not available"
- Verify `DB_ENABLED=true` in environment
- Check that database migrations have been applied
- Ensure database user has SELECT, INSERT, UPDATE, DELETE permissions

### Authentication & Secrets

**Issue**: "Missing Azure AD credentials"
- Verify `AZURE_CLIENT_ID`, `AZURE_TENANT_ID`, `AZURE_CLIENT_SECRET` are set
- Check in `.env` (local) or via `gcloud secrets list` (Cloud Run)
- Follow [AZURE_SETUP.md](AZURE_SETUP.md) to ensure app is registered correctly
- If using Cloud Run secret mounts, verify `--set-secrets` was used in deployment

**Issue**: "Authentication_RequestDenied" or "Insufficient privileges"
- Verify app has `Mail.Send` permission in Microsoft Graph
- Check that admin consent was granted (see AZURE_SETUP.md step 3.7)
- Service account needs permissions to send emails on behalf of `simbyp@sdp.gov.co`

**Issue**: 4-tier secrets loading not working as expected
- Enable debug logging to see which tier was used: `logger.info` messages in `src/config.py`
- Check that environment variables are correctly set in deployment (use `gcloud run services describe simbyp-email-notifications`)
- Verify Secret Manager references are in correct format: `projects/{project_id}/secrets/{secret_id}/versions/latest`
- For Cloud Run secret mounts, check that `/var/run/secrets/cloud.google.com/` directory exists

### Email Delivery

**Issue**: Emails not arriving
- Check Azure AD audit logs for send failures
- Verify `simbyp@sdp.gov.co` email exists in Microsoft 365
- Confirm recipient email addresses are valid
- Check email spam filters

**Issue**: "No recipients configured"
- If using CSV mode: Check the CSV file exists at `RECIPIENTS_CSV_URI` and is formatted correctly
- If using database mode: Verify users have active subscriptions (`/api/users` endpoint)
- Check environment variables `WEEKLY_ALERTS_RECIPIENTS` or `MONTHLY_BUILT_AREA_RECIPIENTS` if using fallback

### Cloud Storage

**Issue**: GCS connection errors
- Verify service account has Storage Object Viewer role on the bucket
- Check `RECIPIENTS_CSV_URI` is correct (uses default from `src/config.py` if not overridden)
- For local dev: set `GOOGLE_APPLICATION_CREDENTIALS` in `.env` to path of service account key
- Check for typos in bucket/file names

**Issue**: Alerts not loading from GCS
- Verify alert files exist in expected GCS locations
- Check service account permissions on alert buckets
- Confirm `DAYS_BACK` setting (default: 20 days) captures expected alerts
- Check GCS file naming conventions match what `AlertProcessor` expects

### General Configuration

**Issue**: Different configuration per environment
- Use environment variables (Tier 1) for environment-specific settings
- Use `.env` for local development (Tier 2)
- Use Google Secret Manager for cloud deployments (Tier 3)
- Defaults from `src/config.py` are used for anything not explicitly set
- For debugging configuration loading, check application logs which show which tier was used

**Issue**: Port conflicts
- Default port is 8080; override with `PORT` environment variable
- For Cloud Run: always use port 8080 (required by Cloud Run)
- For Docker: use `-p 8080:8080` to map ports

## Implementation Status

✅ **Production Ready**: The system is fully implemented and tested on GCP Cloud Run.

### Completed Features

- ✅ **Core Alert System**: Weekly and monthly alerts from GCS
- ✅ **Microsoft 365 Integration**: Email sending via Microsoft Graph API
- ✅ **Database Layer**: PostgreSQL with SQLAlchemy ORM, repository pattern, and connection pooling
- ✅ **Admin Interface**: Browser-based user and subscription management at `/admin`
- ✅ **REST API**: Complete CRUD endpoints for programmatic user management
- ✅ **Audit Logging**: Tracks all subscription and user changes
- ✅ **Multi-mode Recipients**: Database or CSV-based recipient loading
- ✅ **4-Tier Secrets Loading**: Flexible configuration for all deployment scenarios
- ✅ **Cloud SQL Integration**: Full support for Cloud SQL with Unix sockets
- ✅ **Health Checks**: Endpoints for service and database health monitoring
- ✅ **Docker Containerization**: Production-ready Docker configuration
- ✅ **Database Migrations**: Schema management with migration scripts

### Verified Functionality

- ✅ Email sending tested with Microsoft Graph API
- ✅ Recipients loaded from both database and GCS CSV
- ✅ Microsoft 365 integration confirmed and working
- ✅ Alerts loading from GCS buckets confirmed
- ✅ Admin interface CRUD operations verified
- ✅ Database connections stable under load testing
- ✅ Deployment on Cloud Run successful and stable

## Architecture & Design Notes

- **Configuration Strategy**: Non-secret defaults are defined in `src/config.py` for clarity and maintainability. Secrets follow a 4-tier loading pattern: direct environment → .env file → Google Secret Manager → Cloud Run secret mounts. The code automatically detects where each secret comes from and loads it accordingly.

- **Email Delivery**: Uses Microsoft Graph API with service account authentication (application permissions). Emails are sent on behalf of `simbyp@sdp.gov.co` using the organization's Microsoft 365 tenant. Recipients are added to BCC to hide them from each other while preserving delivery traceability.

- **Database Layer**: Uses SQLAlchemy ORM with repository pattern for data access. Connection pooling with automatic health checks ensures reliable database connectivity. Supports both local development (localhost) and Cloud SQL (Unix sockets or private IP).

- **Recipient Management**: Dual-mode system supports both database (recommended) and CSV-based recipient loading. Database mode provides audit logging, subscriptions, and REST API. CSV mode offers simplicity with fallback behavior.

- **Stateless Design**: Each service invocation is independent; no state is maintained between calls. This enables horizontal scaling on Cloud Run.

- **Audit Trail**: All subscription changes are logged with timestamp, user ID, action type, and performer. Supports debugging and compliance requirements.

- **Email Duplicates**: The system processes alerts as-is from GCS. If the same alert appears multiple times, it may be sent multiple times. This is intentional for accuracy.

- **Simple & Lightweight**: No external dependencies beyond standard cloud services (GCS, Secret Manager, Microsoft Graph). Minimal operational overhead.

## Contributing

Daniel Wiesner y Laura Tamayo
