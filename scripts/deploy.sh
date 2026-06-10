#!/bin/bash
set -e

echo "Starting Cloud Run deployment..."
gcloud run deploy simbyp-email-notifications \
  --source . \
  --region us-central1 \
  --allow-unauthenticated \
  --memory=256Mi \
  --timeout=300 \
  --add-cloudsql-instances bosques-bogota-416214:us-central1:simbyp-users-db \
  --set-secrets AZURE_CLIENT_ID=AZURE_CLIENT_ID:latest \
  --set-secrets AZURE_TENANT_ID=AZURE_TENANT_ID:latest \
  --set-secrets AZURE_CLIENT_SECRET=AZURE_CLIENT_SECRET:latest \
  --set-secrets DATABASE_URL=DATABASE_URL:latest \
  --set-env-vars REMOTE_DB_ONLY=true \
  --set-env-vars EXPECTED_CLOUD_SQL_INSTANCE=bosques-bogota-416214:us-central1:simbyp-users-db \
  --service-account="sa-bosques-app@bosques-bogota-416214.iam.gserviceaccount.com" \
  --project=bosques-bogota-416214
echo "Deployment completed successfully!"