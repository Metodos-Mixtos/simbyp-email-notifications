-- Migration 006: Add 'skipped' as a valid reports_sent.status
-- Date: 2026-09-02
-- Description: Lets the send queue mark a generated report (e.g. weekly GFW
-- alerts with zero detections) as intentionally not emailed, instead of
-- either sending an empty-alerts email or leaving it stuck as 'generated'.

DO $$
DECLARE
    existing_name TEXT;
BEGIN
    FOR existing_name IN
        SELECT c.conname
        FROM pg_constraint c
        JOIN pg_class t ON t.oid = c.conrelid
        WHERE t.relname = 'reports_sent'
          AND c.contype = 'c'
          AND pg_get_constraintdef(c.oid) ILIKE '%status%'
          AND pg_get_constraintdef(c.oid) NOT ILIKE '%alert_type%'
    LOOP
        EXECUTE format('ALTER TABLE reports_sent DROP CONSTRAINT %I', existing_name);
    END LOOP;

    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint c
        JOIN pg_class t ON t.oid = c.conrelid
        WHERE t.relname = 'reports_sent'
          AND c.conname = 'check_reports_sent_status'
    ) THEN
        ALTER TABLE reports_sent
            ADD CONSTRAINT check_reports_sent_status
            CHECK (status IN ('generated', 'sent', 'failed', 'partial', 'skipped'));
    END IF;
END $$;
