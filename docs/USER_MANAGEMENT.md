# User Management Guide

Complete guide for managing users and subscriptions in the SIMBYP email notification system.

## Table of Contents

- [Overview](#overview)
- [API Endpoints](#api-endpoints)
- [CLI Tool](#cli-tool)
- [Common Workflows](#common-workflows)
- [Troubleshooting](#troubleshooting)

## Overview

The system provides three ways to manage users:

1. **REST API** - For programmatic access and integrations
2. **CLI Tool** - For administrative tasks and bulk operations
3. **Direct Database** - For advanced operations (use with caution)

## API Endpoints

### Authentication

Currently, API endpoints are **unauthenticated** for internal use. For production, implement authentication (API keys, OAuth, etc.).

### Base URL

```
Local: http://localhost:8080
Production: https://your-cloud-run-url
```

---

### User Management

#### Create User

Create a new user in the system.

**Endpoint:** `POST /api/users`

**Request Body:**
```json
{
  "email": "user@example.com",
  "name": "John Doe",
  "department": "Planning",
  "municipality_code": "11001"
}
```

**Response (201 Created):**
```json
{
  "status": "success",
  "user": {
    "id": "123e4567-e89b-12d3-a456-426614174000",
    "email": "user@example.com",
    "name": "John Doe",
    "department": "Planning",
    "municipality_code": "11001",
    "created_at": "2026-05-22T15:30:00",
    "updated_at": "2026-05-22T15:30:00"
  }
}
```

**cURL Example:**
```bash
curl -X POST https://your-app-url/api/users \
  -H "Content-Type: application/json" \
  -d '{
    "email": "user@example.com",
    "name": "John Doe",
    "department": "Planning",
    "municipality_code": "11001"
  }'
```

---

#### Get User

Get user details by ID.

**Endpoint:** `GET /api/users/:id`

**Response (200 OK):**
```json
{
  "user": {
    "id": "123e4567-e89b-12d3-a456-426614174000",
    "email": "user@example.com",
    "name": "John Doe",
    "department": "Planning",
    "municipality_code": "11001",
    "created_at": "2026-05-22T15:30:00",
    "updated_at": "2026-05-22T15:30:00"
  },
  "subscriptions": [
    {
      "id": "789e4567-e89b-12d3-a456-426614174000",
      "alert_type": "weekly_alerts",
      "is_active": true,
      "subscribed_at": "2026-05-22T15:30:00"
    }
  ]
}
```

**cURL Example:**
```bash
curl https://your-app-url/api/users/123e4567-e89b-12d3-a456-426614174000
```

---

#### List Users

List all users with pagination.

**Endpoint:** `GET /api/users?offset=0&limit=50`

**Query Parameters:**
- `offset` (optional): Number of records to skip (default: 0)
- `limit` (optional): Maximum records to return (default: 100, max: 1000)

**Response (200 OK):**
```json
{
  "users": [
    {
      "id": "123e4567-e89b-12d3-a456-426614174000",
      "email": "user1@example.com",
      "name": "John Doe",
      "department": "Planning",
      "municipality_code": "11001"
    },
    {
      "id": "456e4567-e89b-12d3-a456-426614174000",
      "email": "user2@example.com",
      "name": "Jane Smith",
      "department": "Environment",
      "municipality_code": "11002"
    }
  ],
  "total": 2,
  "offset": 0,
  "limit": 50
}
```

**cURL Example:**
```bash
curl "https://your-app-url/api/users?offset=0&limit=50"
```

---

#### Update User

Update user details.

**Endpoint:** `PUT /api/users/:id`

**Request Body (all fields optional):**
```json
{
  "name": "John Updated Doe",
  "department": "New Department",
  "municipality_code": "11003"
}
```

**Response (200 OK):**
```json
{
  "status": "success",
  "user": {
    "id": "123e4567-e89b-12d3-a456-426614174000",
    "email": "user@example.com",
    "name": "John Updated Doe",
    "department": "New Department",
    "municipality_code": "11003",
    "created_at": "2026-05-22T15:30:00",
    "updated_at": "2026-05-22T16:45:00"
  }
}
```

**cURL Example:**
```bash
curl -X PUT https://your-app-url/api/users/123e4567-e89b-12d3-a456-426614174000 \
  -H "Content-Type: application/json" \
  -d '{"name": "John Updated Doe"}'
```

---

#### Delete User

Delete a user (cascades to subscriptions and audit logs).

**Endpoint:** `DELETE /api/users/:id`

**Response (200 OK):**
```json
{
  "status": "success",
  "message": "User deleted successfully"
}
```

**cURL Example:**
```bash
curl -X DELETE https://your-app-url/api/users/123e4567-e89b-12d3-a456-426614174000
```

---

### Subscription Management

#### Subscribe User

Subscribe user to an alert type.

**Endpoint:** `POST /api/subscriptions`

**Request Body:**
```json
{
  "user_id": "123e4567-e89b-12d3-a456-426614174000",
  "alert_type": "weekly_alerts",
  "performed_by": "admin@example.com"
}
```

**Valid Alert Types:**
- `weekly_alerts` - Weekly deforestation and land cover alerts (every Tuesday)
- `monthly_built_area` - Monthly built area expansion reports (first Friday)

**Response (201 Created):**
```json
{
  "status": "success",
  "subscription": {
    "id": "789e4567-e89b-12d3-a456-426614174000",
    "user_id": "123e4567-e89b-12d3-a456-426614174000",
    "alert_type": "weekly_alerts",
    "is_active": true,
    "subscribed_at": "2026-05-22T15:30:00"
  }
}
```

**cURL Example:**
```bash
curl -X POST https://your-app-url/api/subscriptions \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "123e4567-e89b-12d3-a456-426614174000",
    "alert_type": "weekly_alerts",
    "performed_by": "admin@example.com"
  }'
```

---

#### Unsubscribe User

Unsubscribe user from an alert type.

**Endpoint:** `DELETE /api/subscriptions/:id`

**Request Body:**
```json
{
  "performed_by": "admin@example.com"
}
```

**Response (200 OK):**
```json
{
  "status": "success",
  "message": "Unsubscribed successfully"
}
```

**cURL Example:**
```bash
curl -X DELETE https://your-app-url/api/subscriptions/789e4567-e89b-12d3-a456-426614174000 \
  -H "Content-Type: application/json" \
  -d '{"performed_by": "admin@example.com"}'
```

---

#### Get User Subscriptions

Get all subscriptions for a user.

**Endpoint:** `GET /api/users/:id/subscriptions`

**Response (200 OK):**
```json
{
  "user_id": "123e4567-e89b-12d3-a456-426614174000",
  "subscriptions": [
    {
      "id": "789e4567-e89b-12d3-a456-426614174000",
      "alert_type": "weekly_alerts",
      "is_active": true,
      "subscribed_at": "2026-05-22T15:30:00",
      "unsubscribed_at": null
    },
    {
      "id": "012e4567-e89b-12d3-a456-426614174000",
      "alert_type": "monthly_built_area",
      "is_active": false,
      "subscribed_at": "2026-05-20T10:00:00",
      "unsubscribed_at": "2026-05-21T14:30:00"
    }
  ]
}
```

**cURL Example:**
```bash
curl https://your-app-url/api/users/123e4567-e89b-12d3-a456-426614174000/subscriptions
```

---

#### Toggle Subscription

Activate or deactivate a subscription.

**Endpoint:** `PATCH /api/subscriptions/:id/toggle`

**Request Body:**
```json
{
  "performed_by": "admin@example.com"
}
```

**Response (200 OK):**
```json
{
  "status": "success",
  "subscription": {
    "id": "789e4567-e89b-12d3-a456-426614174000",
    "user_id": "123e4567-e89b-12d3-a456-426614174000",
    "alert_type": "weekly_alerts",
    "is_active": false,
    "subscribed_at": "2026-05-22T15:30:00",
    "unsubscribed_at": "2026-05-22T16:45:00"
  }
}
```

---

## CLI Tool

### Installation

The CLI tool is located at `scripts/manage_users.py`.

```bash
# Make executable
chmod +x scripts/manage_users.py

# Run with Python
python scripts/manage_users.py --help
```

### Commands

#### Add User

```bash
python scripts/manage_users.py add-user \
  --email user@example.com \
  --name "John Doe" \
  --department "Planning" \
  --municipality "11001"
```

#### Remove User

```bash
python scripts/manage_users.py remove-user --email user@example.com
```

#### List Users

```bash
# List all users
python scripts/manage_users.py list-users

# List with pagination
python scripts/manage_users.py list-users --offset 0 --limit 50

# Filter by municipality
python scripts/manage_users.py list-users --municipality 11001
```

#### Subscribe User

```bash
python scripts/manage_users.py subscribe \
  --email user@example.com \
  --alert-type weekly_alerts
```

#### Unsubscribe User

```bash
python scripts/manage_users.py unsubscribe \
  --email user@example.com \
  --alert-type weekly_alerts
```

#### List Subscriptions

```bash
# List all active subscriptions
python scripts/manage_users.py list-subscriptions

# List for specific alert type
python scripts/manage_users.py list-subscriptions --alert-type weekly_alerts
```

#### Import from CSV

```bash
python scripts/manage_users.py import-csv \
  --file /path/to/users.csv \
  --dry-run  # Preview without making changes
```

**CSV Format:**
```csv
email,name,department,municipality_code,weekly_alerts,monthly_built_area
user1@example.com,John Doe,Planning,11001,1,1
user2@example.com,Jane Smith,Environment,11002,1,0
```

#### Export to CSV

```bash
python scripts/manage_users.py export-csv --output users_export.csv
```

#### Interactive Mode

```bash
python scripts/manage_users.py --interactive
```

Launches an interactive menu for easier user management.

---

## Common Workflows

### Workflow 1: Add New User with Subscriptions

```bash
# Step 1: Create user via API
curl -X POST https://your-app-url/api/users \
  -H "Content-Type: application/json" \
  -d '{
    "email": "newuser@example.com",
    "name": "New User",
    "department": "Planning"
  }'

# Response includes user_id: 123e4567-e89b-12d3-a456-426614174000

# Step 2: Subscribe to weekly alerts
curl -X POST https://your-app-url/api/subscriptions \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "123e4567-e89b-12d3-a456-426614174000",
    "alert_type": "weekly_alerts",
    "performed_by": "admin@example.com"
  }'

# Step 3: Subscribe to monthly reports
curl -X POST https://your-app-url/api/subscriptions \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "123e4567-e89b-12d3-a456-426614174000",
    "alert_type": "monthly_built_area",
    "performed_by": "admin@example.com"
  }'
```

### Workflow 2: Bulk Import Users

```bash
# Step 1: Prepare CSV file (users.csv)
# email,name,department,municipality_code,weekly_alerts,monthly_built_area
# user1@example.com,John Doe,Planning,11001,1,1
# user2@example.com,Jane Smith,Environment,11002,1,0

# Step 2: Preview import (dry run)
python scripts/manage_users.py import-csv --file users.csv --dry-run

# Step 3: Perform actual import
python scripts/manage_users.py import-csv --file users.csv
```

### Workflow 3: Migrate from CSV to Database

```bash
# Use the migration script
python scripts/migrate_csv_to_db.py

# This will:
# 1. Read existing CSV from GCS
# 2. Parse and validate user data
# 3. Insert users and subscriptions into database
# 4. Generate migration report
```

### Workflow 4: Update User Department

```bash
curl -X PUT https://your-app-url/api/users/123e4567-e89b-12d3-a456-426614174000 \
  -H "Content-Type: application/json" \
  -d '{"department": "New Department"}'
```

### Workflow 5: Temporarily Disable User Alerts

```bash
# Get user subscriptions
curl https://your-app-url/api/users/123e4567-e89b-12d3-a456-426614174000/subscriptions

# Toggle subscription (deactivate)
curl -X PATCH https://your-app-url/api/subscriptions/789e4567-e89b-12d3-a456-426614174000/toggle \
  -H "Content-Type: application/json" \
  -d '{"performed_by": "admin@example.com"}'

# To reactivate, toggle again
curl -X PATCH https://your-app-url/api/subscriptions/789e4567-e89b-12d3-a456-426614174000/toggle \
  -H "Content-Type: application/json" \
  -d '{"performed_by": "admin@example.com"}'
```

---

## Troubleshooting

### Problem: "User already exists" error

**Cause:** Attempting to create user with duplicate email

**Solution:** 
1. Check if user exists: `GET /api/users?email=user@example.com`
2. Update existing user instead: `PUT /api/users/:id`

---

### Problem: "Database connection failed"

**Cause:** Database not properly initialized or connection string incorrect

**Solution:**
1. Check `DATABASE_URL` environment variable
2. Verify Cloud SQL instance is running
3. Test database health: `GET /health/db`
4. Review logs for connection errors

---

### Problem: Cannot unsubscribe user

**Cause:** Subscription not found or already inactive

**Solution:**
1. Get user subscriptions: `GET /api/users/:id/subscriptions`
2. Verify subscription ID and status
3. If already inactive, no action needed

---

### Problem: Import CSV fails with validation errors

**Cause:** Invalid email format or missing required fields

**Solution:**
1. Validate CSV format matches expected columns
2. Check for valid email addresses
3. Use `--dry-run` flag to preview errors before import
4. Fix errors in CSV and retry

---

### Problem: "Permission denied" when accessing API

**Cause:** Authentication/authorization not configured (future feature)

**Solution:**
Currently, APIs are unauthenticated. For production:
1. Implement API key authentication
2. Add OAuth/JWT tokens
3. Configure IAM permissions

---

## Best Practices

1. **Always specify `performed_by`** when making subscription changes for proper audit trail
2. **Use pagination** when listing large numbers of users
3. **Perform dry-run** before bulk imports to catch errors
4. **Export data regularly** as backup
5. **Monitor audit logs** to track subscription changes
6. **Use email as primary identifier** for user lookups
7. **Test changes in development** before applying to production

---

## References

- [DATABASE.md](DATABASE.md) - Database schema and technical details
- [CLOUD_SQL_SETUP.md](CLOUD_SQL_SETUP.md) - Cloud SQL setup instructions
- [README.md](../README.md) - Main project documentation
