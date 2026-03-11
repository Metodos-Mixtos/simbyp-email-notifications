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
│  ⚠ SENDGRID_API_KEY: sm://SENDGRID_API_KEY                     │
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
  --set-env-vars="SENDGRID_API_KEY=sm://SENDGRID_API_KEY" \
  ...other flags
```

**You DON'T need to set these** (uses defaults from `src/config.py`):
- `GCP_PROJECT_ID` - Already in config
- `FROM_EMAIL` - Already in config  
- `FROM_NAME` - Already in config
- `RECIPIENTS_CSV_URI` - Already in config
- `DAYS_BACK` - Already in config
- `PORT` - Already in config

### 2. Grant Cloud Run Service Account Access to Secret

The secret `SENDGRID_API_KEY` already exists in Secret Manager at:
```
projects/548822075986/secrets/SENDGRID_API_KEY
```

Grant your Cloud Run service account access:
```bash
# Get your service account email
SA_EMAIL=$(gcloud run services describe simbyp-email-notifications \
  --format='value(spec.template.spec.serviceAccountName)')

# Grant secret access
gcloud secrets add-iam-policy-binding SENDGRID_API_KEY \
  --member="serviceAccount:$SA_EMAIL" \
  --role="roles/secretmanager.secretAccessor"
```

Reference it in your deployment:
```bash
--set-env-vars="SENDGRID_API_KEY=sm://SENDGRID_API_KEY"
```

### 3. Grant Other Required Permissions

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

**Option A: Source-based deployment** (Cloud Build builds the Docker image automatically):
```bash
gcloud run deploy simbyp-email-notifications \
  --source . \
  --platform=managed \
  --region=us-central1 \
  --allow-unauthenticated \
  --memory=256Mi \
  --cpu=1 \
  --timeout=300 \
  --max-instances=10 \
  --set-env-vars="SENDGRID_API_KEY=sm://SENDGRID_API_KEY" \
  --service-account="$SA_EMAIL"
```

**Option B: Pre-built image deployment** (build and push manually):
```bash
# Step 1: Build and push to Container Registry
docker buildx build --platform linux/amd64 \
  -t gcr.io/bosques-bogota-416214/simbyp-email-notifications:latest \
  --push .

# Step 2: Deploy the image
gcloud run deploy simbyp-email-notifications \
  --image=gcr.io/bosques-bogota-416214/simbyp-email-notifications:latest \
  --platform=managed \
  --region=us-central1 \
  --allow-unauthenticated \
  --memory=256Mi \
  --cpu=1 \
  --timeout=300 \
  --max-instances=10 \
  --set-env-vars="SENDGRID_API_KEY=sm://SENDGRID_API_KEY" \
  --service-account="$SA_EMAIL"
```

**Recommendation**: Use Option A for simplicity. Cloud Build will automatically build the Docker image from your source code.

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

### Docker Push Authentication Error
If you see: `ERROR: failed to build: failed to solve: error getting credentials`

**Solution**: Configure Docker to authenticate with GCP:
```bash
gcloud auth configure-docker gcr.io
```

Then retry the docker buildx command.

**Better option**: Use source-based deployment (Option A) instead - Cloud Build handles authentication automatically and is simpler.

### Config Validation Error
If you see: `Configuration errors: SENDGRID_API_KEY is not set`

**Solution:**
```bash
gcloud run deploy ... --set-env-vars="SENDGRID_API_KEY=sm://SENDGRID_API_KEY"
```

### Different Values per Environment  
Create environment-specific deployments:

**Production:**
```bash
gcloud run deploy simbyp-email-notifications-prod \
  --set-env-vars="RECIPIENTS_CSV_URI=gs://prod-bucket/recipients.csv" \
  --set-env-vars="SENDGRID_API_KEY=sm://SENDGRID_API_KEY"
```

**Staging:**
```bash
gcloud run deploy simbyp-email-notifications-staging \
  --set-env-vars="RECIPIENTS_CSV_URI=gs://staging-bucket/recipients.csv" \
  --set-env-vars="SENDGRID_API_KEY=sm://SENDGRID_API_KEY"
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

