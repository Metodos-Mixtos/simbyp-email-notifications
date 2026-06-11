-- SIMBYP Email Notifications - Report Tracking Schema
-- PostgreSQL 15+
-- Version: 002
-- Description: Adds tables for tracking reports sent, recipients, and alert statistics

-- ============================================================================
-- REPORTS_SENT TABLE
-- Tracks every email report sent by the system
-- ============================================================================
CREATE TABLE reports_sent (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    alert_type VARCHAR(50) NOT NULL CHECK (alert_type IN ('weekly_alerts', 'monthly_built_area')),
    report_title VARCHAR(500) NOT NULL,
    report_url TEXT,
    report_date DATE,
    sent_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
    recipient_count INTEGER DEFAULT 0,
    status VARCHAR(20) DEFAULT 'sent' CHECK (status IN ('generated', 'sent', 'failed', 'partial')),
    error_message TEXT,
    metadata JSONB
);

-- Indexes for reports_sent
CREATE INDEX idx_reports_sent_alert_type ON reports_sent(alert_type);
CREATE INDEX idx_reports_sent_sent_at ON reports_sent(sent_at DESC);
CREATE INDEX idx_reports_sent_status ON reports_sent(status);
CREATE INDEX idx_reports_sent_report_date ON reports_sent(report_date);

-- Comments
COMMENT ON TABLE reports_sent IS 'Log of all email reports sent by the system';
COMMENT ON COLUMN reports_sent.alert_type IS 'Type of alert sent (weekly_alerts or monthly_built_area)';
COMMENT ON COLUMN reports_sent.report_title IS 'Title of the report from GCS metadata';
COMMENT ON COLUMN reports_sent.report_url IS 'GCS path or URL to the report';
COMMENT ON COLUMN reports_sent.report_date IS 'Date the report covers (not when it was sent)';
COMMENT ON COLUMN reports_sent.recipient_count IS 'Number of recipients who received this report';
COMMENT ON COLUMN reports_sent.status IS 'Overall status: sent (all succeeded), partial (some failed), failed (all failed)';
COMMENT ON COLUMN reports_sent.metadata IS 'Additional metadata in JSON format (alert counts, sources, etc.)';

-- ============================================================================
-- REPORT_RECIPIENTS TABLE
-- Tracks which users received which reports and delivery status
-- ============================================================================
CREATE TABLE report_recipients (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    report_id UUID NOT NULL REFERENCES reports_sent(id) ON DELETE CASCADE,
    user_id UUID REFERENCES users(id) ON DELETE SET NULL,
    email VARCHAR(255) NOT NULL,
    delivered_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    delivery_status VARCHAR(20) DEFAULT 'sent' CHECK (delivery_status IN ('queued', 'sent', 'failed', 'bounced')),
    error_message TEXT
);

-- Indexes for report_recipients
CREATE INDEX idx_report_recipients_report_id ON report_recipients(report_id);
CREATE INDEX idx_report_recipients_user_id ON report_recipients(user_id);
CREATE INDEX idx_report_recipients_email ON report_recipients(email);
CREATE INDEX idx_report_recipients_delivered_at ON report_recipients(delivered_at DESC);
CREATE INDEX idx_report_recipients_status ON report_recipients(delivery_status);

-- Comments
COMMENT ON TABLE report_recipients IS 'Individual delivery log for each recipient per report';
COMMENT ON COLUMN report_recipients.user_id IS 'Reference to user (NULL if user was deleted)';
COMMENT ON COLUMN report_recipients.email IS 'Email address (denormalized for history preservation)';
COMMENT ON COLUMN report_recipients.delivery_status IS 'Delivery status: queued, sent, failed, bounced';

-- ============================================================================
-- ALERT_STATISTICS TABLE
-- Aggregate statistics about alerts by date and type
-- ============================================================================
CREATE TABLE alert_statistics (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    date DATE NOT NULL,
    alert_type VARCHAR(50) NOT NULL,
    alert_source VARCHAR(50),
    alert_count INTEGER DEFAULT 0,
    municipality_code VARCHAR(10),
    metadata JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for alert_statistics
CREATE INDEX idx_alert_stats_date ON alert_statistics(date DESC);
CREATE INDEX idx_alert_stats_type ON alert_statistics(alert_type);
CREATE INDEX idx_alert_stats_source ON alert_statistics(alert_source);
CREATE INDEX idx_alert_stats_municipality ON alert_statistics(municipality_code);
CREATE UNIQUE INDEX idx_alert_stats_unique ON alert_statistics(date, alert_type, alert_source, COALESCE(municipality_code, ''));

-- Comments
COMMENT ON TABLE alert_statistics IS 'Daily aggregate statistics about alerts';
COMMENT ON COLUMN alert_statistics.alert_type IS 'Type of alert (weekly_alerts, monthly_built_area, etc.)';
COMMENT ON COLUMN alert_statistics.alert_source IS 'Source of alert data (gfw, psa, urban_sprawl)';
COMMENT ON COLUMN alert_statistics.alert_count IS 'Number of alerts for this date/type/source combination';
COMMENT ON COLUMN alert_statistics.municipality_code IS 'Municipality code if alert is location-specific';
COMMENT ON COLUMN alert_statistics.metadata IS 'Additional metrics in JSON format';

-- ============================================================================
-- ANALYTICS VIEWS
-- ============================================================================

-- View: Recent reports with recipient counts
CREATE VIEW recent_reports AS
SELECT 
    rs.id,
    rs.alert_type,
    rs.report_title,
    rs.report_date,
    rs.sent_at,
    rs.recipient_count,
    rs.status,
    COUNT(rr.id) as actual_recipients,
    SUM(CASE WHEN rr.delivery_status = 'sent' THEN 1 ELSE 0 END) as successful_deliveries,
    SUM(CASE WHEN rr.delivery_status = 'failed' THEN 1 ELSE 0 END) as failed_deliveries
FROM reports_sent rs
LEFT JOIN report_recipients rr ON rs.id = rr.report_id
GROUP BY rs.id, rs.alert_type, rs.report_title, rs.report_date, rs.sent_at, rs.recipient_count, rs.status
ORDER BY rs.sent_at DESC;

COMMENT ON VIEW recent_reports IS 'Reports with delivery statistics';

-- View: Reports by month
CREATE VIEW reports_by_month AS
SELECT 
    DATE_TRUNC('month', sent_at) as month,
    alert_type,
    COUNT(*) as report_count,
    SUM(recipient_count) as total_recipients,
    AVG(recipient_count) as avg_recipients_per_report
FROM reports_sent
WHERE status = 'sent'
GROUP BY DATE_TRUNC('month', sent_at), alert_type
ORDER BY month DESC, alert_type;

COMMENT ON VIEW reports_by_month IS 'Monthly summary of reports sent';

-- View: User delivery history
CREATE VIEW user_delivery_history AS
SELECT 
    u.id as user_id,
    u.email,
    u.name,
    COUNT(rr.id) as total_reports_received,
    MAX(rr.delivered_at) as last_report_received,
    SUM(CASE WHEN rr.delivery_status = 'sent' THEN 1 ELSE 0 END) as successful_deliveries,
    SUM(CASE WHEN rr.delivery_status = 'failed' THEN 1 ELSE 0 END) as failed_deliveries
FROM users u
LEFT JOIN report_recipients rr ON u.id = rr.user_id
GROUP BY u.id, u.email, u.name
ORDER BY total_reports_received DESC;

COMMENT ON VIEW user_delivery_history IS 'Delivery statistics per user';

-- View: Alert trends
CREATE VIEW alert_trends AS
SELECT 
    date,
    alert_type,
    alert_source,
    SUM(alert_count) as total_alerts
FROM alert_statistics
GROUP BY date, alert_type, alert_source
ORDER BY date DESC, alert_type, alert_source;

COMMENT ON VIEW alert_trends IS 'Daily alert trends by type and source';

-- View: Weekly alert summary (last 30 days)
CREATE VIEW weekly_alert_summary AS
SELECT 
    DATE_TRUNC('week', date) as week_start,
    alert_type,
    alert_source,
    SUM(alert_count) as weekly_alerts,
    COUNT(DISTINCT date) as days_with_alerts
FROM alert_statistics
WHERE date >= CURRENT_DATE - INTERVAL '30 days'
GROUP BY DATE_TRUNC('week', date), alert_type, alert_source
ORDER BY week_start DESC, alert_type;

COMMENT ON VIEW weekly_alert_summary IS 'Weekly alert summary for last 30 days';

-- ============================================================================
-- HELPER FUNCTIONS
-- ============================================================================

-- Function: Get delivery rate for a report
CREATE OR REPLACE FUNCTION get_report_delivery_rate(report_uuid UUID)
RETURNS DECIMAL(5,2) AS $$
DECLARE
    total_count INTEGER;
    success_count INTEGER;
BEGIN
    SELECT COUNT(*), SUM(CASE WHEN delivery_status = 'sent' THEN 1 ELSE 0 END)
    INTO total_count, success_count
    FROM report_recipients
    WHERE report_id = report_uuid;
    
    IF total_count = 0 THEN
        RETURN 0.0;
    END IF;
    
    RETURN (success_count::DECIMAL / total_count) * 100;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION get_report_delivery_rate IS 'Calculate delivery success rate for a report (returns percentage)';

-- Function: Get user engagement score
CREATE OR REPLACE FUNCTION get_user_engagement_score(user_uuid UUID)
RETURNS DECIMAL(5,2) AS $$
DECLARE
    total_sent INTEGER;
    total_received INTEGER;
BEGIN
    -- Count how many reports were sent in periods when user was subscribed
    -- vs how many they actually received (to detect delivery issues)
    SELECT 
        COUNT(DISTINCT rs.id) as sent,
        COUNT(rr.id) as received
    INTO total_sent, total_received
    FROM reports_sent rs
    LEFT JOIN report_recipients rr ON rs.id = rr.report_id AND rr.user_id = user_uuid
    WHERE rs.sent_at >= (SELECT created_at FROM users WHERE id = user_uuid);
    
    IF total_sent = 0 THEN
        RETURN 0.0;
    END IF;
    
    RETURN (total_received::DECIMAL / total_sent) * 100;
END;
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION get_user_engagement_score IS 'Calculate what percentage of reports user received since joining';

-- ============================================================================
-- Sample Analytics Queries
-- ============================================================================

-- These are example queries - not executable, just documentation

/*
-- 1. Reports sent in last 7 days
SELECT * FROM recent_reports 
WHERE sent_at >= CURRENT_DATE - INTERVAL '7 days';

-- 2. Delivery rate by alert type
SELECT 
    alert_type,
    COUNT(*) as total_reports,
    AVG(recipient_count) as avg_recipients,
    ROUND(AVG(get_report_delivery_rate(id)), 2) as avg_delivery_rate
FROM reports_sent
WHERE sent_at >= CURRENT_DATE - INTERVAL '30 days'
GROUP BY alert_type;

-- 3. Users with failed deliveries
SELECT 
    u.email,
    u.name,
    COUNT(*) as failed_count,
    MAX(rr.delivered_at) as last_failure
FROM users u
JOIN report_recipients rr ON u.id = rr.user_id
WHERE rr.delivery_status = 'failed'
GROUP BY u.id, u.email, u.name
HAVING COUNT(*) > 2
ORDER BY failed_count DESC;

-- 4. Alert trends by municipality
SELECT 
    municipality_code,
    alert_type,
    SUM(alert_count) as total_alerts
FROM alert_statistics
WHERE date >= CURRENT_DATE - INTERVAL '30 days'
GROUP BY municipality_code, alert_type
ORDER BY total_alerts DESC;

-- 5. Most active report recipients
SELECT * FROM user_delivery_history
WHERE total_reports_received > 0
ORDER BY total_reports_received DESC
LIMIT 10;
*/
