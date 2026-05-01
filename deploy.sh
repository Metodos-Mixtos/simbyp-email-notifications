#!/bin/bash
set -e
echo "Starting Cloud Run deployment..."
gcloud run deploy simbyp-email-notifications \
  --source . \
  --region us-central1 \
  --allow-unauthenticated \
  --memory=256Mi \
  --timeout=300 \
  --set-secrets SENDGRID_API_KEY=SENDGRID_API_KEY:latest \
  --service-account="sa-bosques-app@bosques-bogota-416214.iam.gserviceaccount.com" \
  --project=bosques-bogota-416214
echo "Deployment completed successfully!"
