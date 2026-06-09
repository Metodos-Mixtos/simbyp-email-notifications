-- SIMBYP Email Notifications - Initial Database Schema
-- PostgreSQL 15+
-- Version: 001
-- Description: Creates users, subscriptions, and audit tables

-- Enable UUID extension
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ============================================================================
-- USERS TABLE
-- Stores user information for email recipients
-- ============================================================================
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) UNIQUE NOT NULL,
    name VARCHAR(255),
    department VARCHAR(255),
    municipality_code VARCHAR(10),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for performance
CREATE INDEX idx_users_email ON users(email);
CREATE INDEX idx_users_municipality ON users(municipality_code);

-- Comments for documentation
COMMENT ON TABLE users IS 'Email recipients for SIMBYP alert notifications';
COMMENT ON COLUMN users.email IS 'Primary email address (unique identifier)';
COMMENT ON COLUMN users.municipality_code IS 'Colombian municipality DIVIPOLA code';

-- ============================================================================
-- SUBSCRIPTIONS TABLE
-- Manages user subscriptions to different alert types
-- ============================================================================
CREATE TABLE subscriptions (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    alert_type VARCHAR(50) NOT NULL CHECK (alert_type IN ('weekly_alerts', 'monthly_built_area')),
    is_active BOOLEAN DEFAULT TRUE,
    subscribed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    unsubscribed_at TIMESTAMP,
    UNIQUE(user_id, alert_type)
);

-- Indexes for query performance
CREATE INDEX idx_subscriptions_user_id ON subscriptions(user_id);
CREATE INDEX idx_subscriptions_alert_type ON subscriptions(alert_type);
CREATE INDEX idx_subscriptions_active ON subscriptions(is_active);
CREATE INDEX idx_subscriptions_lookup ON subscriptions(alert_type, is_active);

-- Comments for documentation
COMMENT ON TABLE subscriptions IS 'User subscriptions to alert types';
COMMENT ON COLUMN subscriptions.alert_type IS 'Type of alert: weekly_alerts or monthly_built_area';
COMMENT ON COLUMN subscriptions.is_active IS 'Whether subscription is currently active';

-- ============================================================================
-- SUBSCRIPTION_AUDIT TABLE
-- Audit trail for subscription changes
-- ============================================================================
CREATE TABLE subscription_audit (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    alert_type VARCHAR(50) NOT NULL,
    action VARCHAR(20) NOT NULL CHECK (action IN ('subscribed', 'unsubscribed', 'reactivated')),
    performed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    performed_by VARCHAR(255),
    notes TEXT
);

-- Indexes for audit queries
CREATE INDEX idx_audit_user_id ON subscription_audit(user_id);
CREATE INDEX idx_audit_performed_at ON subscription_audit(performed_at);
CREATE INDEX idx_audit_action ON subscription_audit(action);

-- Comments for documentation
COMMENT ON TABLE subscription_audit IS 'Audit log of all subscription changes';
COMMENT ON COLUMN subscription_audit.performed_by IS 'Email or system identifier that made the change';

-- ============================================================================
-- TRIGGER: Update updated_at timestamp
-- ============================================================================
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_users_updated_at
    BEFORE UPDATE ON users
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- ============================================================================
-- HELPER VIEWS
-- ============================================================================

-- View: Active subscriptions with user details
CREATE VIEW active_subscriptions AS
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

COMMENT ON VIEW active_subscriptions IS 'All active user subscriptions with user details';

-- View: Weekly alerts recipients
CREATE VIEW weekly_alerts_recipients AS
SELECT 
    u.id,
    u.email,
    u.name,
    u.municipality_code
FROM users u
JOIN subscriptions s ON u.id = s.user_id
WHERE s.alert_type = 'weekly_alerts' AND s.is_active = TRUE
ORDER BY u.email;

COMMENT ON VIEW weekly_alerts_recipients IS 'Active recipients for weekly alerts (deforestation + land cover)';

-- View: Monthly built area recipients
CREATE VIEW monthly_built_area_recipients AS
SELECT 
    u.id,
    u.email,
    u.name,
    u.municipality_code
FROM users u
JOIN subscriptions s ON u.id = s.user_id
WHERE s.alert_type = 'monthly_built_area' AND s.is_active = TRUE
ORDER BY u.email;

COMMENT ON VIEW monthly_built_area_recipients IS 'Active recipients for monthly built area reports';

-- ============================================================================
-- Initial Data (optional test users)
-- ============================================================================
-- Uncomment to add test users during development
-- INSERT INTO users (email, name, department) VALUES 
-- ('admin@sdp.gov.co', 'Admin User', 'Technology'),
-- ('test@sdp.gov.co', 'Test User', 'Planning');
