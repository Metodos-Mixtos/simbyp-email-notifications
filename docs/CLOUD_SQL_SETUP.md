# Cloud SQL Setup Guide

This guide walks you through setting up Cloud SQL PostgreSQL for the SIMBYP email notifications user management system.

## Prerequisites

- GCP project: `bosques-bogota-416214`
- gcloud CLI installed and authenticated
- Appropriate IAM permissions:
  - `cloudsql.admin` or `cloudsql.instances.create`
  - `cloudsql.databases.create`
  - `cloudsql.users.create`

## Step 1: Create Cloud SQL Instance

### Option A: Using gcloud CLI with Public IP (Recommended for Getting Started)

```bash
# Set project
gcloud config set project bosques-bogota-416214

# Create PostgreSQL instance with public IP
gcloud sql instances create simbyp-users-db \
  --database-version=POSTGRES_15 \
  --tier=db-f1-micro \
  --region=us-central1 \
  --storage-type=SSD \
  --storage-size=10GB \
  --storage-auto-increase \
  --backup-start-time=03:00 \
  --retained-backups-count=7 \
  --database-flags=max_connections=100

# Then add your IP for security
MY_IP=$(curl -s https://api.ipify.org)
gcloud sql instances patch simbyp-users-db \
  --authorized-networks=$MY_IP/32
```

**Note**: Creation takes 5-10 minutes. Monitor progress with:
```bash
gcloud sql operations list --instance=simbyp-users-db --limit=5
```

### Option B: Using gcloud CLI with Private IP (More Secure, Requires VPC Setup)

If you want private IP only (more secure but requires additional setup):

```bash
# Step 1: Enable Service Networking API
gcloud services enable servicenetworking.googleapis.com

# Step 2: Allocate IP range for private connection
gcloud compute addresses create google-managed-services-default \
  --global \
  --purpose=VPC_PEERING \
  --prefix-length=16 \
  --network=default

# Step 3: Create private service connection
gcloud services vpc-peerings connect \
  --service=servicenetworking.googleapis.com \
  --ranges=google-managed-services-default \
  --network=default

# Step 4: Create PostgreSQL instance with private IP only
gcloud sql instances create simbyp-users-db \
  --database-version=POSTGRES_15 \
  --tier=db-f1-micro \
  --region=us-central1 \
  --storage-type=SSD \
  --storage-size=10GB \
  --storage-auto-increase \
  --backup-start-time=03:00 \
  --retained-backups-count=7 \
  --database-flags=max_connections=100 \
  --network=projects/bosques-bogota-416214/global/networks/default \
  --no-assign-ip
```

### Option C: Using GCP Console

1. Go to [Cloud SQL](https://console.cloud.google.com/sql/instances) in GCP Console
2. Click "CREATE INSTANCE"
3. Choose "PostgreSQL"
4. Configure:
   - **Instance ID**: `simbyp-users-db`
   - **Password**: Set root password (save in Secret Manager)
   - **Database version**: PostgreSQL 15
   - **Region**: us-central1
   - **Zonal availability**: Single zone
   - **Machine type**: Lightweight (1 vCPU, 0.6 GB)
   - **Storage**: SSD, 10 GB, enable automatic increase
   - **Connections**: Private IP (recommended)
   - **Backups**: Automated daily backups, 7 days retention
5. Click "CREATE INSTANCE"

## Step 2: Create Database


```bash
# Create the simbyp_db database
gcloud sql databases create simbyp_db \
  --instance=simbyp-users-db

# Verify creation
gcloud sql databases list --instance=simbyp-users-db
```

## Step 3: Create Database User

```bash
# Create application user with strong password
# Replace YOUR_SECURE_PASSWORD with a generated password
gcloud sql users create simbyp_app \
  --instance=simbyp-users-db \
  --password=YOUR_SECURE_PASSWORD

# Verify user creation
gcloud sql users list --instance=simbyp-users-db
```

**Important**: Store the password in Google Secret Manager:
```bash
echo -n "YOUR_SECURE_PASSWORD" | gcloud secrets create DB_PASSWORD \
  --data-file=- \
  --replication-policy=automatic
```

## Step 4: Configure Connection Security

### For Public IP (Option A)

You've already added your IP to authorized networks. For Cloud Run access:

```bash
# Cloud Run doesn't need IP authorization - it uses IAM
# Just ensure your service account has cloudsql.client role (done in Step 6)
```

### For Private IP (Option B)

Already configured during instance creation (see Option B above).

### Additional Security (Optional)

If you need to add more IPs to authorized networks:

```bash
# Add your IP to authorized networks
gcloud sql instances patch simbyp-users-db \
  --authorized-networks=YOUR_IP_ADDRESS/32
```

## Step 5: Apply Database Schema

### Using Cloud Shell or Local Machine

```bash
# Get connection name
export INSTANCE_CONNECTION_NAME=$(gcloud sql instances describe simbyp-users-db \
  --format="value(connectionName)")

echo "Connection name: $INSTANCE_CONNECTION_NAME"

# Connect via Cloud SQL Proxy
# Download proxy if needed:
# curl -o cloud-sql-proxy https://storage.googleapis.com/cloud-sql-connectors/cloud-sql-proxy/v2.8.0/cloud-sql-proxy.linux.amd64
# chmod +x cloud-sql-proxy

# Start proxy in background
./cloud-sql-proxy $INSTANCE_CONNECTION_NAME &
PROXY_PID=$!

# Wait for proxy to be ready
sleep 5

# Apply schema
psql "host=127.0.0.1 port=5432 dbname=simbyp_db user=simbyp_app" \
  -f migrations/001_initial_schema.sql

# Stop proxy
kill $PROXY_PID
```

### Alternative: Using gcloud sql connect

```bash
# Connect interactively
gcloud sql connect simbyp-users-db --user=postgres --database=simbyp_db

# Then paste the contents of migrations/001_initial_schema.sql
# Or use \i command:
\i /path/to/migrations/001_initial_schema.sql
```

## Step 6: Grant IAM Permissions

Grant service account access to Cloud SQL:

```bash
# Get service account email
SERVICE_ACCOUNT="sa-bosques-app@bosques-bogota-416214.iam.gserviceaccount.com"

# Grant Cloud SQL Client role
gcloud projects add-iam-policy-binding bosques-bogota-416214 \
  --member="serviceAccount:${SERVICE_ACCOUNT}" \
  --role="roles/cloudsql.client"

# Grant Secret Manager access for DB password
gcloud secrets add-iam-policy-binding DB_PASSWORD \
  --member="serviceAccount:${SERVICE_ACCOUNT}" \
  --role="roles/secretmanager.secretAccessor"
```

## Step 7: Store Connection Details in Secret Manager

```bash
# Store database connection string
echo -n "postgresql://simbyp_app:YOUR_PASSWORD@/simbyp_db?host=/cloudsql/$INSTANCE_CONNECTION_NAME" | \
  gcloud secrets create DATABASE_URL \
  --data-file=- \
  --replication-policy=automatic

# Or for TCP connection (if using private IP):
echo -n "postgresql://simbyp_app:YOUR_PASSWORD@PRIVATE_IP:5432/simbyp_db" | \
  gcloud secrets create DATABASE_URL \
  --data-file=- \
  --replication-policy=automatic
```

## Step 8: Verify Setup

```bash
# Test connection
gcloud sql connect simbyp-users-db --user=simbyp_app --database=simbyp_db

# Inside psql:
\dt          # List tables
\dv          # List views
SELECT * FROM users LIMIT 1;
\q           # Exit
```

## Connection Strings Reference

### Cloud Run (Unix Socket)
```
postgresql://simbyp_app:PASSWORD@/simbyp_db?host=/cloudsql/bosques-bogota-416214:us-central1:simbyp-users-db
```

### Private IP (VPC)
```
postgresql://simbyp_app:PASSWORD@PRIVATE_IP:5432/simbyp_db
```

### Cloud SQL Proxy (Local Development)
```
postgresql://simbyp_app:PASSWORD@127.0.0.1:5432/simbyp_db
```

## Environment Variables

Add to your `.env` file for local development:

```bash
# Database Configuration
DATABASE_URL=postgresql://simbyp_app:PASSWORD@127.0.0.1:5432/simbyp_db
DB_ENABLED=true

# Or individual components:
DB_HOST=127.0.0.1
DB_PORT=5432
DB_NAME=simbyp_db
DB_USER=simbyp_app
DB_PASSWORD=YOUR_PASSWORD
```

## Cost Estimation

- **db-f1-micro instance**: ~$7-10/month
- **10GB SSD storage**: ~$1.70/month
- **Backups (7 days)**: ~$0.20/month
- **Total**: ~$9-12/month

To reduce costs:
- Delete instance when not needed: `gcloud sql instances delete simbyp-users-db`
- Stop instance temporarily: `gcloud sql instances patch simbyp-users-db --activation-policy=NEVER`

## Troubleshooting

### Connection timeout
- Check firewall rules if using public IP
- Verify VPC peering if using private IP
- Ensure Cloud SQL Proxy is running for local development

### Authentication failed
- Verify password in Secret Manager
- Check user exists: `gcloud sql users list --instance=simbyp-users-db`
- Reset password if needed: `gcloud sql users set-password simbyp_app --instance=simbyp-users-db --password=NEW_PASSWORD`

### Schema application failed
- Check PostgreSQL version compatibility (requires 15+)
- Verify pgcrypto extension is available
- Check user has CREATE privileges

### IAM permission errors
- Verify service account has `cloudsql.client` role
- Check Secret Manager permissions for password access
- Ensure service account is specified in Cloud Run deployment

## Next Steps

After Cloud SQL setup is complete:
1. Update `src/config.py` with database configuration
2. Run CSV migration script to import existing users
3. Deploy application to Cloud Run with Cloud SQL connection
4. Test user management endpoints

See [DATABASE.md](DATABASE.md) for schema details and [USER_MANAGEMENT.md](USER_MANAGEMENT.md) for management operations.
