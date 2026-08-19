-- Migration 004: Add reporte_paramos as valid alert_type
-- Allows users to subscribe to paramos reports from Dynamic World service
-- Date: 2026-08-19

-- Drop existing CHECK constraint
ALTER TABLE subscriptions DROP CONSTRAINT IF EXISTS check_alert_type;

-- Add new CHECK constraint with reporte_paramos
ALTER TABLE subscriptions ADD CONSTRAINT check_alert_type 
    CHECK (alert_type IN ('weekly_alerts', 'monthly_built_area', 'reporte_paramos'));

-- Drop existing CHECK constraint on reports_sent
ALTER TABLE reports_sent DROP CONSTRAINT IF EXISTS check_alert_type_reports;

-- Add new CHECK constraint with reporte_paramos to reports_sent
ALTER TABLE reports_sent ADD CONSTRAINT check_alert_type_reports 
    CHECK (alert_type IN ('weekly_alerts', 'monthly_built_area', 'reporte_paramos'));

-- Add comment documenting the change
COMMENT ON TABLE subscriptions IS 
'User subscription to alert types. 
Alert types: weekly_alerts (deforestation alerts), monthly_built_area (urban growth), reporte_paramos (dynamic world paramos monitoring)';
