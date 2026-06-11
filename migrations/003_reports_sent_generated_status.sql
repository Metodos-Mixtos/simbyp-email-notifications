-- SIMBYP Email Notifications - Migration 003
-- PostgreSQL 15+
-- Description: Ensure reports_sent.status supports 'generated' for DB-first email queue selection

DO $$
DECLARE
    existing_name TEXT;
BEGIN
    -- Drop any existing status check constraint over reports_sent so we can replace it safely.
    FOR existing_name IN
        SELECT c.conname
        FROM pg_constraint c
        JOIN pg_class t ON t.oid = c.conrelid
        WHERE t.relname = 'reports_sent'
          AND c.contype = 'c'
          AND pg_get_constraintdef(c.oid) ILIKE '%status%'
    LOOP
        EXECUTE format('ALTER TABLE reports_sent DROP CONSTRAINT %I', existing_name);
    END LOOP;

    -- Recreate explicit status constraint including generated.
    IF NOT EXISTS (
        SELECT 1
        FROM pg_constraint c
        JOIN pg_class t ON t.oid = c.conrelid
        WHERE t.relname = 'reports_sent'
          AND c.conname = 'check_reports_sent_status'
    ) THEN
        ALTER TABLE reports_sent
            ADD CONSTRAINT check_reports_sent_status
            CHECK (status IN ('generated', 'sent', 'failed', 'partial'));
    END IF;
END $$;
