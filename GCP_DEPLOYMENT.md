# GCP Cloud Run Deployment Guide

## Problem Fixed
The codebase now separates **configuration defaults** (in code) from **secrets and environment-specific overrides**:
- Non-secret defaults are defined in `src/config.py` ✅
- Secrets are managed in Google Secret Manager
- `.env` file is optional (local development only)

## Configuration Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    Application Defaults                         │
│              (Defined in src/config.py)                         │
│  ✓ GCP_PROJECT_ID: bosques-bogota-416214                        │
│  ✓ FROM_EMAIL: simbyp@sdp.gov.co                                │
│  ✓ FROM_NAME: SIMBYP Alertas                                    │
│  ✓ RECIPIENTS_CSV_URI: gs://material-estatico-sdp/...           │
│  ✓ DAYS_BACK: 20                                                │
│  ✓ PORT: 8080                                                   │
└─────────────────────────────────────────────────────────────────┘
                            │
                            ├─ (Override via environment variables if needed)
                            │
┌─────────────────────────────────────────────────────────────────┐
│               Secrets & Environment Overrides                    │
│            (Environment variables / Secret Manager)              │
│  ⚠ SENDGRID_API_KEY: sm://sendgrid-api-key                      │
│  ⚠ GOOGLE_APPLICATION_CREDENTIALS: (auto in Cloud Run)          │
│  ⚠ Custom overrides for other environments                       │
└─────────────────────────────────────────────────────────────────┘
```

## Local Development

Your `.env` file should only contain **secrets** and **environment-specific overrides**:

```dotenv
# ./env (LOCAL DEV ONLY - never commit secrets!)
SENDGRID_API_KEY=your-actual-key
GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account-key.json

# Optional: override defaults if needed
# GCP_PROJECT_ID=different-project-for-testing
# DAYS_BACK=10
```

Run locally:
```bash
source venv/bin/activate
python main.py
```

The app will:
1. Load `.env` (if it exists)
2. Use defaults from `src/config.py` for everything not in `.env`
3. Validate required config on startup

## GCP Cloud Run Deployment

### 1. Set Up Environment Variables

When deploying, only set variables that differ from defaults or are secrets:

```bash
gcloud run deploy simbyp-email-notifications \
  --set-env-vars="SENDGRID_API_KEY=sm://sendgrid-api-key" \
  ...other flags
```

**You DON'T need to set these** (uses defaults from `src/config.py`):
- `GCP_PROJECT_ID` - Already in config
- `FROM_EMAIL` - Already in config  
- `FROM_NAME` - Already in config
- `RECIPIENTS_CSV_URI` - Already in config
- `DAYS_BACK` - Already in config
- `PORT` - Already in config

### 2. Set Up Secrets in Secret Manager

Store sensitive values:

```bash
# Create a secret for SendGrid API key
echo -n "SG.actual-api-key..." | \
  gcloud secrets create sendgrid-api-key --data-file=-

# Grant Cloud Run service account access
gcloud secrets add-iam-policy-binding sendgrid-api-key \
  --member="serviceAccount:YOUR-SERVICE-ACCOUNT@appspot.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"
```

Reference it in your deployment:
```bash
--set-env-vars="SENDGRID_API_KEY=sm://sendgrid-api-key"
```

### 3. Service Account Permissions

Assign roles to your Cloud Run service account:

```bash
# Get your service account email
SA_EMAIL=$(gcloud run services describe simbyp-email-notifications \
  --format='value(spec.template.spec.serviceAccountName)')

# Grant storage permissions (read GCS buckets)
gcloud projects add-iam-policy-binding bosques-bogota-416214 \
  --member="serviceAccount:$SA_EMAIL" \
  --role="roles/storage.objectViewer"

# Grant secret access
gcloud projects add-iam-policy-binding bosques-bogota-416214 \
  --member="serviceAccount:$SA_EMAIL" \
  --role="roles/secretmanager.secretAccessor"
```

### 4. Example Full Deployment

```bash
gcloud run deploy simbyp-email-notifications \
  --image=gcr.io/bosques-bogota-416214/simbyp-email-notifications:latest \
  --platform=managed \
  --region=us-central1 \
  --memory=512Mi \
  --cpu=1 \
  --timeout=3600 \
  --max-instances=10 \
  --set-env-vars="SENDGRID_API_KEY=sm://sendgrid-api-key" \
  --service-account="$SA_EMAIL"
```

## Configuration Reference

| Variable | Default | Required | Managed By |
|----------|---------|----------|-----------|
| `GCP_PROJECT_ID` | `bosques-bogota-416214` | No* | Code |
| `FROM_EMAIL` | `simbyp@sdp.gov.co` | No | Code |
| `FROM_NAME` | `SIMBYP Alertas` | No | Code |
| `RECIPIENTS_CSV_URI` | GCS URI as shown | No* | Code |
| `DAYS_BACK` | `20` | No | Code |
| `PORT` | `8080` | No | Code |
| `SENDGRID_API_KEY` | None | **Yes** | Secret Manager |
| `VALIDATE_CONFIG` | `true` | No | Code |

*Can be overridden via environment variables if needed for different environments

## Troubleshooting

### Config Validation Error
If you see: `Configuration errors: SENDGRID_API_KEY is not set`

**Solution:**
```bash
gcloud run deploy ... --set-env-vars="SENDGRID_API_KEY=sm://your-secret-name"
```

### Different Values per Environment  
Create environment-specific deployments:

**Production:**
```bash
gcloud run deploy simbyp-email-notifications-prod \
  --set-env-vars="RECIPIENTS_CSV_URI=gs://prod-bucket/recipients.csv" \
  --set-env-vars="SENDGRID_API_KEY=sm://sendgrid-api-key-prod"
```

**Staging:**
```bash
gcloud run deploy simbyp-email-notifications-staging \
  --set-env-vars="RECIPIENTS_CSV_URI=gs://staging-bucket/recipients.csv" \
  --set-env-vars="SENDGRID_API_KEY=sm://sendgrid-api-key-staging"
```

## Best Practices

✅ **DO:**
- Keep defaults in `src/config.py` for non-secrets
- Use Secret Manager for API keys and sensitive values  
- Set environment variables only for environment-specific overrides
- `.gitignore` your `.env` file

❌ **DON'T:**
- Commit real API keys to git
- Hardcode secrets in code
- Use environment variables for stable defaults (put in code instead)
- Create `.env` files in production (Cloud Run won't read them)

