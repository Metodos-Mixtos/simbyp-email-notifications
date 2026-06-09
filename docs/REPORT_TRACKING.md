# Report Tracking Feature - Implementation Summary

## Overview

Extended the SIMBYP email notification database to track:
- **Reports sent** - Every email report with delivery status
- **Report recipients** - Individual delivery logs per recipient
- **Alert statistics** - Daily aggregate metrics for alerts

## ✅ Completed Components

### 1. Database Schema Extension (`migrations/002_reports_tracking.sql`)

**Three new tables:**

#### `reports_sent`
- Logs every email report sent
- Tracks alert type, title, URL, recipient count
- Status: sent, failed, partial
- JSONB metadata for flexible data storage

#### `report_recipients`
- Individual delivery record per recipient
- Links to users (with soft delete support)
- Denormalized email for history preservation
- Delivery status: queued, sent, failed, bounced

#### `alert_statistics`
- Daily aggregate alert counts
- By type, source, and municipality
- Supports GFW, PSA, and urban sprawl data
- JSONB metadata for additional metrics

**Five analytics views:**
- `recent_reports` - Reports with delivery statistics
- `reports_by_month` - Monthly summary
- `user_delivery_history` - Per-user delivery stats
- `alert_trends` - Daily alert trends
- `weekly_alert_summary` - Last 30 days by week

**Two helper functions:**
- `get_report_delivery_rate(report_id)` - Calculate success rate
- `get_user_engagement_score(user_id)` - Calculate user engagement

### 2. ORM Models

**Three new models in `src/models/`:**

#### `ReportSent` (`report.py`)
- Full model for reports_sent table
- Factory methods: `create_weekly_report()`, `create_monthly_report()`
- Status methods: `mark_as_sent()`, `mark_as_failed()`, `mark_as_partial()`
- Relationship to ReportRecipient

#### `ReportRecipient` (`report_recipient.py`)
- Model for report_recipients table
- Factory method: `create_for_user()`
- Status methods: `mark_as_sent()`, `mark_as_failed()`, `mark_as_bounced()`
- Relationships to User and ReportSent

#### `AlertStatistic` (`alert_statistic.py`)
- Model for alert_statistics table
- Factory methods: `create_gfw_stat()`, `create_psa_stat()`, `create_urban_sprawl_stat()`
- Unique constraint per date/type/source/municipality

### 3. Repository Layer (`src/repositories/report_repository.py`)

**Comprehensive ReportRepository with methods for:**

#### Report Logging
- `log_report_sent()` - Log successful report with recipients
- `log_report_failure()` - Log failed report attempt
- `update_delivery_status()` - Update individual recipient status

#### Report Queries
- `get_report_by_id()` - Get report with recipients
- `list_recent_reports()` - Recent reports (default 30 days)
- `list_reports_by_type()` - Filter by alert type
- `get_delivery_rate()` - Calculate success percentage

#### Recipient Queries
- `get_user_report_history()` - User's delivery history
- `get_failed_deliveries()` - Recent failures for debugging

#### Alert Statistics
- `log_alert_statistic()` - Log/update daily stats (upsert)
- `get_alert_trends()` - Recent trends with filters
- `get_total_alerts_by_type()` - Aggregates by date range

#### Analytics
- `get_reports_summary()` - Overall statistics
- `get_user_engagement_score()` - User engagement metric

## 📊 Usage Examples

### Log a Sent Report

```python
from src.database import get_db_session
from src.repositories import ReportRepository

with get_db_session() as session:
    repo = ReportRepository(session)
    
    # Log weekly report sent
    report = repo.log_report_sent(
        alert_type='weekly_alerts',
        report_title='Alertas GFW - I Trimestre 2026',
        recipient_emails=['user1@example.com', 'user2@example.com'],
        report_url='gs://bucket/report.html',
        metadata={'deforestation_alerts': 5, 'land_cover_alerts': 3}
    )
    
    session.commit()
    print(f"Report logged: {report.id}")
```

### Log Alert Statistics

```python
from datetime import date
from src.repositories import ReportRepository

with get_db_session() as session:
    repo = ReportRepository(session)
    
    # Log GFW alerts for today
    stat = repo.log_alert_statistic(
        date=date.today(),
        alert_type='deforestation',
        alert_source='gfw',
        alert_count=15,
        municipality_code='11001',
        metadata={'affected_area_ha': 25.5}
    )
    
    session.commit()
```

### Query Analytics

```python
# Get delivery summary for last 30 days
summary = repo.get_reports_summary(days=30)
print(f"Sent: {summary['reports'].get('sent', 0)} reports")
print(f"Total recipients: {summary['total_recipients']}")
print(f"Successful deliveries: {summary['deliveries'].get('sent', 0)}")

# Get alert trends
trends = repo.get_alert_trends(days=30, alert_type='deforestation')
for trend in trends:
    print(f"{trend.date}: {trend.alert_count} alerts from {trend.alert_source}")

# Check user engagement
score = repo.get_user_engagement_score(user_id)
print(f"User receives {score}% of reports since joining")
```

## 🔄 Integration Points

### Where to Integrate Report Logging

**In `src/email_service.py`** (to be implemented):

```python
def send_weekly_report(self, recipients, weekly_report):
    """Send weekly report and log to database."""
    
    # Send email (existing logic)
    success = self._send_email(recipients, weekly_report)
    
    # Log to database (NEW)
    if DB_ENABLED:
        with get_db_session() as session:
            repo = ReportRepository(session)
            
            if success:
                repo.log_report_sent(
                    alert_type='weekly_alerts',
                    report_title=weekly_report['title'],
                    recipient_emails=recipients,
                    report_url=weekly_report.get('url'),
                    metadata={
                        'deforestation_alerts': len(weekly_report.get('deforestation', [])),
                        'land_cover_alerts': len(weekly_report.get('land_cover', []))
                    }
                )
            else:
                repo.log_report_failure(
                    alert_type='weekly_alerts',
                    report_title=weekly_report['title'],
                    error_message='Email send failed'
                )
            
            session.commit()
    
    return success
```

### Where to Log Alert Statistics

**In `src/alerts_processor.py`** (to be implemented):

```python
def get_latest_weekly_alerts_report(self):
    """Get weekly report and log statistics."""
    
    # Get report (existing logic)
    report = self._fetch_report_from_gcs()
    
    # Log statistics (NEW)
    if DB_ENABLED and report:
        with get_db_session() as session:
            repo = ReportRepository(session)
            
            # Log GFW alerts
            if report.get('deforestation_count'):
                repo.log_alert_statistic(
                    date=date.today(),
                    alert_type='deforestation',
                    alert_source='gfw',
                    alert_count=report['deforestation_count']
                )
            
            # Log PSA alerts
            if report.get('land_cover_count'):
                repo.log_alert_statistic(
                    date=date.today(),
                    alert_type='land_cover',
                    alert_source='psa',
                    alert_count=report['land_cover_count']
                )
            
            session.commit()
    
    return report
```

## 📈 Analytics Queries

### View Recent Reports with Delivery Stats

```sql
SELECT * FROM recent_reports 
WHERE sent_at >= CURRENT_DATE - INTERVAL '7 days'
ORDER BY sent_at DESC;
```

### Monthly Report Summary

```sql
SELECT * FROM reports_by_month
WHERE month >= DATE_TRUNC('month', CURRENT_DATE - INTERVAL '6 months');
```

### Find Users with Delivery Issues

```sql
SELECT 
    email,
    name,
    total_reports_received,
    failed_deliveries
FROM user_delivery_history
WHERE failed_deliveries > 2
ORDER BY failed_deliveries DESC;
```

### Alert Trends by Source

```sql
SELECT 
    date,
    alert_source,
    SUM(alert_count) as daily_total
FROM alert_statistics
WHERE date >= CURRENT_DATE - INTERVAL '30 days'
GROUP BY date, alert_source
ORDER BY date DESC, alert_source;
```

### Delivery Success Rate

```sql
SELECT 
    alert_type,
    COUNT(*) as total_reports,
    AVG(get_report_delivery_rate(id)) as avg_delivery_rate
FROM reports_sent
WHERE sent_at >= CURRENT_DATE - INTERVAL '30 days'
GROUP BY alert_type;
```

## 🎯 Benefits

1. **Audit Trail** - Complete history of every email sent
2. **Debugging** - "Did user get the email?" is now answerable
3. **Analytics** - Understand alert patterns and trends
4. **Quality Monitoring** - Track delivery failures
5. **User Engagement** - Identify inactive users or delivery issues
6. **Compliance** - Documentation of what was sent to whom and when
7. **Performance Metrics** - Measure system effectiveness

## 💾 Storage Impact

**Estimated storage (1 year):**
- Reports: ~50 reports/week × 52 weeks = 2,600 records (~1 MB)
- Recipients: 2,600 reports × 50 recipients = 130,000 records (~15 MB)
- Statistics: 365 days × 3 sources × 10 municipalities = ~10,000 records (~2 MB)
- **Total: ~18 MB/year**

**Very minimal impact on db-f1-micro instance.**

## 🔜 Next Steps

To complete the integration:

1. **Update email_service.py** - Add report logging calls
2. **Update alerts_processor.py** - Add statistics logging
3. **Create analytics endpoints** - Expose via API
4. **Add to documentation** - Update USER_MANAGEMENT.md
5. **Create analytics dashboard** - Simple web view (optional)

## 📊 Example Analytics Dashboard Data

```python
# Get data for dashboard
with get_db_session() as session:
    repo = ReportRepository(session)
    
    dashboard_data = {
        'summary': repo.get_reports_summary(days=30),
        'recent_reports': repo.list_recent_reports(days=7, limit=10),
        'alert_trends': repo.get_alert_trends(days=30),
        'failed_deliveries': repo.get_failed_deliveries(days=7)
    }
```

## 🎉 Feature Complete!

All database infrastructure for report tracking is now in place and ready for integration with the email sending logic.
