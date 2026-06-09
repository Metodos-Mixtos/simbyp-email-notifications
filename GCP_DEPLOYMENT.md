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
│  ⚠ AZURE_CLIENT_ID: projects/.../secrets/.../latest            │
│  ⚠ AZURE_TENANT_ID: projects/.../secrets/.../latest            │
│  ⚠ AZURE_CLIENT_SECRET: projects/.../secrets/.../latest        │
│  ⚠ GOOGLE_APPLICATION_CREDENTIALS: (auto in Cloud Run)          │
│  ⚠ Custom overrides for other environments                       │
└─────────────────────────────────────────────────────────────────┘
```

## Local Development

Your `.env` file should only contain **secrets** and **environment-specific overrides**:

```dotenv
# ./env (LOCAL DEV ONLY - never commit secrets!)
AZURE_CLIENT_ID=your-azure-client-id
AZURE_TENANT_ID=your-azure-tenant-id
AZURE_CLIENT_SECRET=your-azure-client-secret
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

### 1. First Deployment: Grant Service Account Access to Secrets

Before deploying, set up the service account that Cloud Run will use. The secrets for Azure AD credentials should exist in Secret Manager.

**Important**: Do this FIRST, before the service exists. We'll use the default Cloud Run service account:

```bash
# Set your project ID
PROJECT_ID="bosques-bogota-416214"

# Grant the Cloud Run default service account access to Azure AD secrets
gcloud secrets add-iam-policy-binding AZURE_CLIENT_ID \
  --member="serviceAccount:${PROJECT_ID}@appspot.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"

gcloud secrets add-iam-policy-binding AZURE_TENANT_ID \
  --member="serviceAccount:${PROJECT_ID}@appspot.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"

gcloud secrets add-iam-policy-binding AZURE_CLIENT_SECRET \
  --member="serviceAccount:${PROJECT_ID}@appspot.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"

# Also grant storage access for reading GCS buckets
gcloud projects add-iam-policy-binding ${PROJECT_ID} \
  --member="serviceAccount:${PROJECT_ID}@appspot.gserviceaccount.com" \
  --role="roles/storage.objectViewer"
```

### 2. Deploy with Secret Reference

You have two options for handling Azure AD credentials:

**Option A: Using Cloud Run's built-in secret injection (RECOMMENDED)**
```bash
gcloud run deploy simbyp-email-notifications \
  --source . \
  --region us-central1 \
  --allow-unauthenticated \
  --memory=256Mi \
  --timeout=300 \
  --set-secrets="AZURE_CLIENT_ID=AZURE_CLIENT_ID:latest" \
  --set-secrets="AZURE_TENANT_ID=AZURE_TENANT_ID:latest" \
  --set-secrets="AZURE_CLIENT_SECRET=AZURE_CLIENT_SECRET:latest" \
  --service-account="sa-bosques-app@bosques-bogota-416214.iam.gserviceaccount.com"
```

**Option B: Using environment variables with Secret Manager reference**
The Python code will automatically detect and load secrets from Secret Manager if you pass the full path with proper version format:
```bash
gcloud run deploy simbyp-email-notifications \
  --source . \
  --region us-central1 \
  --allow-unauthenticated \
  --memory=256Mi \
  --timeout=300 \
  --set-env-vars="AZURE_CLIENT_ID=projects/548822075986/secrets/AZURE_CLIENT_ID/versions/latest" \
  --set-env-vars="AZURE_TENANT_ID=projects/548822075986/secrets/AZURE_TENANT_ID/versions/latest" \
  --set-env-vars="AZURE_CLIENT_SECRET=projects/548822075986/secrets/AZURE_CLIENT_SECRET/versions/latest" \
  --service-account="sa-bosques-app@bosques-bogota-416214.iam.gserviceaccount.com"
```

**Note:** The secret path format must follow: `projects/{PROJECT_ID}/secrets/{SECRET_ID}/versions/{VERSION}`
- ✅ Correct: `projects/548822075986/secrets/AZURE_CLIENT_ID/versions/latest`
- ❌ Wrong: `projects/548822075986/secrets/AZURE_CLIENT_ID/latest`

The code in `src/config.py` detects when values look like secret references (start with `projects/`) and automatically loads the actual secret value from Secret Manager.

**Both options work, but Option A is Cloud Run's recommended pattern.**

### 3. Verify Secret Access After First Deployment

After deploying, verify the service account has access:

```bash
# Get the actual service account email used
SA_EMAIL=$(gcloud run services describe simbyp-email-notifications \
  --region us-central1 \
  --format='value(spec.template.spec.serviceAccountName)')

echo "Service Account: $SA_EMAIL"

# Verify secret access for Azure credentials
gcloud secrets get-iam-policy AZURE_CLIENT_ID --flatten="bindings[].members" \
  --filter="bindings.role:roles/secretmanager.secretAccessor"
```

### 4. One-Command Full Deployment

```bash
gcloud run deploy simbyp-email-notifications \
  --source . \
  --region us-central1 \
  --allow-unauthenticated \
  --memory=256Mi \
  --timeout=300 \
  --set-env-vars="AZURE_CLIENT_ID=projects/548822075986/secrets/AZURE_CLIENT_ID/versions/latest" \
  --set-env-vars="AZURE_TENANT_ID=projects/548822075986/secrets/AZURE_TENANT_ID/versions/latest" \
  --set-env-vars="AZURE_CLIENT_SECRET=projects/548822075986/secrets/AZURE_CLIENT_SECRET/versions/latest" \
  --service-account="sa-bosques-app@bosques-bogota-416214.iam.gserviceaccount.com"
```
```

This command:
- Builds the Docker image automatically using Cloud Build
- Deploys to Cloud Run
- References the secret via its full path (Cloud Run automatically injects it as an environment variable)
- Uses the default Cloud Run service account (which you already granted permissions to)

## Configuration Reference

| Variable | Default | Required | Managed By |
|----------|---------|----------|-----------|
| `GCP_PROJECT_ID` | `bosques-bogota-416214` | No* | Code |
| `FROM_EMAIL` | `simbyp@sdp.gov.co` | No | Code |
| `FROM_NAME` | `SIMBYP Alertas` | No | Code |
| `RECIPIENTS_CSV_URI` | GCS URI as shown | No* | Code |
| `DAYS_BACK` | `20` | No | Code |
| `PORT` | `8080` | No | Code |
| `AZURE_CLIENT_ID` | None | **Yes** | Secret Manager |
| `AZURE_TENANT_ID` | None | **Yes** | Secret Manager |
| `AZURE_CLIENT_SECRET` | None | **Yes** | Secret Manager |
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

### Secret Not Available at Deployment Time
If you see: `Deployment failed` or Azure credentials errors

**Causes:**
1. Service account doesn't have Secret Manager access
2. Secret reference path is incorrect

**Solution:**
Verify permissions are granted:
```bash
PROJECT_ID="bosques-bogota-416214"

# Grant secret access to all Azure AD secrets
for SECRET in AZURE_CLIENT_ID AZURE_TENANT_ID AZURE_CLIENT_SECRET; do
  gcloud secrets add-iam-policy-binding $SECRET \
    --member="serviceAccount:${PROJECT_ID}@appspot.gserviceaccount.com" \
    --role="roles/secretmanager.secretAccessor"
done

# Verify it worked
gcloud secrets get-iam-policy AZURE_CLIENT_ID
```

Then redeploy.

### Different Values per Environment  
Create environment-specific deployments:

**Production:**
```bash
gcloud run deploy simbyp-email-notifications-prod \
  --set-env-vars="RECIPIENTS_CSV_URI=gs://prod-bucket/recipients.csv" \
  --set-secrets="AZURE_CLIENT_ID=AZURE_CLIENT_ID:latest" \
  --set-secrets="AZURE_TENANT_ID=AZURE_TENANT_ID:latest" \
  --set-secrets="AZURE_CLIENT_SECRET=AZURE_CLIENT_SECRET:latest"
```

**Staging:**
```bash
gcloud run deploy simbyp-email-notifications-staging \
  --set-env-vars="RECIPIENTS_CSV_URI=gs://staging-bucket/recipients.csv" \
  --set-secrets="AZURE_CLIENT_ID=AZURE_CLIENT_ID:latest" \
  --set-secrets="AZURE_TENANT_ID=AZURE_TENANT_ID:latest" \
  --set-secrets="AZURE_CLIENT_SECRET=AZURE_CLIENT_SECRET:latest"
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

## Deployment Status

✅ **Current Status**: Production Ready (Cloud Run Revision: 00016-xww)

**Verified Working:**
- Service Account: `sa-bosques-app@bosques-bogota-416214.iam.gserviceaccount.com` with proper permissions
- Secret Manager integration: Secrets automatically loaded and injected
- Email sending: Tested and confirmed (Microsoft Graph API status HTTP 202)
- Recipients: 4 verified recipients loaded from GCS CSV
- Alerts: Built area alerts loading from GCS buckets
- All endpoints operational

**Latest Deployment:**
```
gcloud run deploy simbyp-email-notifications \
  --source . \
  --region us-central1 \
  --allow-unauthenticated \
  --memory=256Mi \
  --timeout=300 \
  --set-env-vars="AZURE_CLIENT_ID=projects/548822075986/secrets/AZURE_CLIENT_ID/versions/latest" \
  --set-env-vars="AZURE_TENANT_ID=projects/548822075986/secrets/AZURE_TENANT_ID/versions/latest" \
  --set-env-vars="AZURE_CLIENT_SECRET=projects/548822075986/secrets/AZURE_CLIENT_SECRET/versions/latest" \
  --service-account="sa-bosques-app@bosques-bogota-416214.iam.gserviceaccount.com"
```

