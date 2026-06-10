#!/bin/bash
set -e

echo "Starting Cloud Run deployment..."
gcloud run deploy simbyp-email-notifications \
  --source . \
  --region us-central1 \
  --allow-unauthenticated \
  --memory=256Mi \
  --timeout=300 \
  --set-secrets AZURE_CLIENT_ID=AZURE_CLIENT_ID:latest \
  --set-secrets AZURE_TENANT_ID=AZURE_TENANT_ID:latest \
  --set-secrets AZURE_CLIENT_SECRET=AZURE_CLIENT_SECRET:latest \
  --service-account="sa-bosques-app@bosques-bogota-416214.iam.gserviceaccount.com" \
  --project=bosques-bogota-416214
echo "Deployment completed successfully!"
