-- Migration 005: Add trimestral_alerts as valid alert_type
-- Date: 2026-08-24

DO $$
DECLARE
    existing_name TEXT;
BEGIN
    -- Rebuild subscriptions alert_type CHECK constraint safely.
    FOR existing_name IN
        SELECT c.conname
        FROM pg_constraint c
        JOIN pg_class t ON t.oid = c.conrelid
        WHERE t.relname = 'subscriptions'
          AND c.contype = 'c'
          AND pg_get_constraintdef(c.oid) ILIKE '%alert_type%'
    LOOP
        EXECUTE format('ALTER TABLE subscriptions DROP CONSTRAINT %I', existing_name);
    END LOOP;

    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint c
        JOIN pg_class t ON t.oid = c.conrelid
        WHERE t.relname = 'subscriptions'
          AND c.conname = 'check_alert_type'
    ) THEN
        ALTER TABLE subscriptions
            ADD CONSTRAINT check_alert_type
            CHECK (alert_type IN ('weekly_alerts', 'monthly_built_area', 'trimestral_alerts', 'reporte_paramos'));
    END IF;

    -- Rebuild reports_sent alert_type CHECK constraint safely.
    FOR existing_name IN
        SELECT c.conname
        FROM pg_constraint c
        JOIN pg_class t ON t.oid = c.conrelid
        WHERE t.relname = 'reports_sent'
          AND c.contype = 'c'
          AND pg_get_constraintdef(c.oid) ILIKE '%alert_type%'
    LOOP
        EXECUTE format('ALTER TABLE reports_sent DROP CONSTRAINT %I', existing_name);
    END LOOP;

    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint c
        JOIN pg_class t ON t.oid = c.conrelid
        WHERE t.relname = 'reports_sent'
          AND c.conname = 'check_alert_type_reports'
    ) THEN
        ALTER TABLE reports_sent
            ADD CONSTRAINT check_alert_type_reports
            CHECK (alert_type IN ('weekly_alerts', 'monthly_built_area', 'trimestral_alerts', 'reporte_paramos'));
    END IF;
END $$;

COMMENT ON COLUMN subscriptions.alert_type IS
'Type of alert: weekly_alerts, monthly_built_area, trimestral_alerts, reporte_paramos';

COMMENT ON COLUMN reports_sent.alert_type IS
'Type of alert sent: weekly_alerts, monthly_built_area, trimestral_alerts, reporte_paramos';
