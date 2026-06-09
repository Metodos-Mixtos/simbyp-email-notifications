# Database Documentation

## Overview

The SIMBYP email notification system uses **PostgreSQL 15+** on Google Cloud SQL for managing user subscriptions to environmental alert notifications.

## Database Schema

### Tables

#### `users`
Stores email recipients for SIMBYP alert notifications.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | UUID | PRIMARY KEY | Unique identifier (auto-generated) |
| `email` | VARCHAR(255) | UNIQUE, NOT NULL | Primary email address |
| `name` | VARCHAR(255) | | User's full name |
| `department` | VARCHAR(255) | | Department or organization |
| `municipality_code` | VARCHAR(10) | | Colombian municipality DIVIPOLA code |
| `created_at` | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | Creation timestamp |
| `updated_at` | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | Last update timestamp (auto-updated) |

**Indexes:**
- `idx_users_email` on `email`
- `idx_users_municipality` on `municipality_code`

#### `subscriptions`
Manages user subscriptions to different alert types.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | UUID | PRIMARY KEY | Unique identifier (auto-generated) |
| `user_id` | UUID | FOREIGN KEY → users(id), NOT NULL | Reference to user |
| `alert_type` | VARCHAR(50) | NOT NULL, CHECK | Type of alert (see Alert Types below) |
| `is_active` | BOOLEAN | DEFAULT TRUE | Whether subscription is currently active |
| `subscribed_at` | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | When user subscribed |
| `unsubscribed_at` | TIMESTAMP | | When user unsubscribed (NULL if active) |

**Constraints:**
- UNIQUE constraint on `(user_id, alert_type)` - one subscription per user per alert type
- CHECK constraint on `alert_type IN ('weekly_alerts', 'monthly_built_area')`
- CASCADE DELETE on user deletion

**Indexes:**
- `idx_subscriptions_user_id` on `user_id`
- `idx_subscriptions_alert_type` on `alert_type`
- `idx_subscriptions_active` on `is_active`
- `idx_subscriptions_lookup` on `(alert_type, is_active)` - for recipient queries

#### `subscription_audit`
Audit trail for all subscription changes.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | UUID | PRIMARY KEY | Unique identifier (auto-generated) |
| `user_id` | UUID | FOREIGN KEY → users(id), NOT NULL | Reference to user |
| `alert_type` | VARCHAR(50) | NOT NULL | Alert type affected |
| `action` | VARCHAR(20) | NOT NULL, CHECK | Action performed (see Actions below) |
| `performed_at` | TIMESTAMP | DEFAULT CURRENT_TIMESTAMP | When action was performed |
| `performed_by` | VARCHAR(255) | | Who made the change (email or 'system') |
| `notes` | TEXT | | Additional notes about the change |

**Actions:**
- `subscribed` - User subscribed to an alert type
- `unsubscribed` - User unsubscribed from an alert type
- `reactivated` - Previously unsubscribed user reactivated subscription

**Indexes:**
- `idx_audit_user_id` on `user_id`
- `idx_audit_performed_at` on `performed_at`
- `idx_audit_action` on `action`

### Views

#### `active_subscriptions`
All active user subscriptions with user details.

```sql
SELECT 
    u.id as user_id,
    u.email,
    u.name,
    u.department,
    u.municipality_code,
    s.alert_type,
    s.subscribed_at
FROM users u
JOIN subscriptions s ON u.id = s.user_id
WHERE s.is_active = TRUE
ORDER BY u.email, s.alert_type;
```

#### `weekly_alerts_recipients`
Active recipients for weekly alerts (deforestation + land cover).

```sql
SELECT 
    u.id,
    u.email,
    u.name,
    u.municipality_code
FROM users u
JOIN subscriptions s ON u.id = s.user_id
WHERE s.alert_type = 'weekly_alerts' AND s.is_active = TRUE
ORDER BY u.email;
```

#### `monthly_built_area_recipients`
Active recipients for monthly built area reports.

```sql
SELECT 
    u.id,
    u.email,
    u.name,
    u.municipality_code
FROM users u
JOIN subscriptions s ON u.id = s.user_id
WHERE s.alert_type = 'monthly_built_area' AND s.is_active = TRUE
ORDER BY u.email;
```

## Alert Types

The system supports two types of email alerts:

| Alert Type | Frequency | Description |
|------------|-----------|-------------|
| `weekly_alerts` | Every Tuesday | Deforestation (GFW) + Land Cover (PSA) alerts |
| `monthly_built_area` | First Friday of month | Built area expansion alerts |

## Entity Relationships

```
┌─────────────────┐
│     users       │
│─────────────────│
│ id (PK)         │
│ email (UNIQUE)  │
│ name            │
│ department      │
│ municipality    │
│ created_at      │
│ updated_at      │
└────────┬────────┘
         │
         │ 1:N
         │
┌────────▼────────────────┐
│   subscriptions         │
│─────────────────────────│
│ id (PK)                 │
│ user_id (FK) ───────────┤
│ alert_type              │
│ is_active               │
│ subscribed_at           │
│ unsubscribed_at         │
└─────────────────────────┘
         │
         │ 1:N
         │
┌────────▼────────────────┐
│  subscription_audit     │
│─────────────────────────│
│ id (PK)                 │
│ user_id (FK) ───────────┤
│ alert_type              │
│ action                  │
│ performed_at            │
│ performed_by            │
│ notes                   │
└─────────────────────────┘
```

## Connection Configuration

### Environment Variables

```bash
# Option 1: Full connection string
DATABASE_URL=postgresql://user:password@host:port/database

# Option 2: Individual components
DB_HOST=127.0.0.1
DB_PORT=5432
DB_NAME=simbyp_db
DB_USER=simbyp_app
DB_PASSWORD=your_password
```

### Connection Strings

#### Cloud Run (Unix Socket)
```
postgresql://simbyp_app:PASSWORD@/simbyp_db?host=/cloudsql/bosques-bogota-416214:us-central1:simbyp-users-db
```

#### Private IP (VPC)
```
postgresql://simbyp_app:PASSWORD@10.x.x.x:5432/simbyp_db
```

#### Cloud SQL Proxy (Local Dev)
```
postgresql://simbyp_app:PASSWORD@127.0.0.1:5432/simbyp_db
```

## Performance Considerations

### Connection Pooling

The application uses SQLAlchemy's QueuePool with:
- **Pool size**: 5 connections
- **Max overflow**: 10 additional connections
- **Pool pre-ping**: Validates connections before use
- **Pool recycle**: 3600 seconds (1 hour)

### Indexes

All queries use appropriate indexes:
- Email lookups: `idx_users_email`
- Recipient queries: `idx_subscriptions_lookup` (alert_type, is_active)
- Audit queries: `idx_audit_performed_at`, `idx_audit_user_id`

### Query Optimization

- Use views for common recipient queries
- Pagination with OFFSET/LIMIT for large result sets
- Eager loading with `joinedload()` for relationships
- Connection pooling prevents connection overhead

## Backup and Recovery

### Automated Backups

Cloud SQL performs automated daily backups at 3:00 AM UTC with 7-day retention.

### Manual Backup

```bash
# Create on-demand backup
gcloud sql backups create --instance=simbyp-users-db

# List backups
gcloud sql backups list --instance=simbyp-users-db

# Restore from backup
gcloud sql backups restore BACKUP_ID --backup-instance=simbyp-users-db --backup-id=BACKUP_ID
```

### Export Data

```bash
# Export to Cloud Storage
gcloud sql export sql simbyp-users-db gs://your-bucket/backup.sql \
  --database=simbyp_db
```

### Import Data

```bash
# Import from Cloud Storage
gcloud sql import sql simbyp-users-db gs://your-bucket/backup.sql \
  --database=simbyp_db
```

## Maintenance

### Database Health Check

```bash
# Via API endpoint
curl https://your-cloud-run-url/health/db

# Via psql
psql "postgresql://simbyp_app:PASSWORD@HOST:5432/simbyp_db" -c "SELECT 1;"
```

### View Statistics

```sql
-- User statistics
SELECT COUNT(*) as total_users FROM users;

-- Subscription statistics by type
SELECT 
    alert_type,
    COUNT(*) as total_subscriptions,
    SUM(CASE WHEN is_active THEN 1 ELSE 0 END) as active_subscriptions
FROM subscriptions
GROUP BY alert_type;

-- Recent audit activity
SELECT 
    action,
    COUNT(*) as count,
    MAX(performed_at) as last_occurrence
FROM subscription_audit
WHERE performed_at > NOW() - INTERVAL '7 days'
GROUP BY action;
```

### Cleanup Old Audit Logs (Optional)

```sql
-- Delete audit logs older than 1 year
DELETE FROM subscription_audit 
WHERE performed_at < NOW() - INTERVAL '1 year';
```

## Migrations

Database schema migrations are managed in the `migrations/` directory:

- `001_initial_schema.sql` - Initial database schema

### Apply Migration

```bash
# Connect to database
psql "postgresql://simbyp_app:PASSWORD@HOST:5432/simbyp_db"

# Apply migration
\i migrations/001_initial_schema.sql
```

## Security

### Credentials Storage

- Database passwords stored in Google Secret Manager
- Connection strings loaded via 3-tier pattern (env → .env → Secret Manager)
- Never commit passwords to source control

### IAM Permissions

Required roles for service account:
- `roles/cloudsql.client` - Connect to Cloud SQL
- `roles/secretmanager.secretAccessor` - Read database credentials

### Connection Security

- Private IP recommended (VPC peering)
- SSL/TLS encryption for all connections
- No public IP exposure in production

## Troubleshooting

### Connection Issues

**Problem**: Cannot connect to database

**Solutions**:
1. Verify `DATABASE_URL` is set correctly
2. Check Cloud SQL instance is running
3. Verify service account has `cloudsql.client` role
4. For local dev, ensure Cloud SQL Proxy is running

### Performance Issues

**Problem**: Slow queries

**Solutions**:
1. Check index usage: `EXPLAIN ANALYZE your_query;`
2. Verify connection pool settings
3. Monitor Cloud SQL metrics in GCP Console
4. Consider read replicas for high traffic

### Migration Failures

**Problem**: Schema migration fails

**Solutions**:
1. Check PostgreSQL version (requires 15+)
2. Verify user has CREATE permissions
3. Review error logs: `gcloud sql operations list --instance=simbyp-users-db`
4. Rollback and retry if needed

## Monitoring

### Cloud SQL Metrics

Monitor in GCP Console:
- CPU utilization
- Memory utilization
- Active connections
- Query execution time
- Storage usage

### Application Metrics

Log key database operations:
- Connection pool status
- Query execution time
- Failed queries
- Audit log entries

## Cost Optimization

### Current Configuration
- **Instance**: db-f1-micro (~$7/month)
- **Storage**: 10GB SSD (~$1.70/month)
- **Backups**: 7-day retention (~$0.20/month)
- **Total**: ~$9-12/month

### Cost Reduction Strategies
1. Stop instance when not needed (dev/test)
2. Use smaller storage size
3. Reduce backup retention period
4. Delete unused audit logs periodically

## References

- [Cloud SQL Documentation](https://cloud.google.com/sql/docs/postgres)
- [SQLAlchemy Documentation](https://docs.sqlalchemy.org/)
- [PostgreSQL Documentation](https://www.postgresql.org/docs/15/)
- [CLOUD_SQL_SETUP.md](CLOUD_SQL_SETUP.md) - Detailed setup instructions
- [USER_MANAGEMENT.md](USER_MANAGEMENT.md) - User management operations
