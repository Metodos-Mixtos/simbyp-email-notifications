#!/usr/bin/env python
"""Apply migration 004 to add reporte_paramos to subscriptions and reports_sent."""

from sqlalchemy import text
from src.database import init_db, get_db_session
from src.config import DATABASE_URL

print("Initializing database connection...")
init_db(DATABASE_URL)

sql_statements = [
    "ALTER TABLE subscriptions DROP CONSTRAINT IF EXISTS check_alert_type;",
    "ALTER TABLE subscriptions ADD CONSTRAINT check_alert_type CHECK (alert_type IN ('weekly_alerts', 'monthly_built_area', 'reporte_paramos'));",
    "ALTER TABLE reports_sent DROP CONSTRAINT IF EXISTS check_alert_type_reports;",
    "ALTER TABLE reports_sent ADD CONSTRAINT check_alert_type_reports CHECK (alert_type IN ('weekly_alerts', 'monthly_built_area', 'reporte_paramos'));",
]

print("Applying migration...")
with get_db_session() as session:
    for sql in sql_statements:
        session.execute(text(sql))
        print(f"✓ Executed: {sql[:70]}...")
    session.commit()

print("✓ Migration applied successfully!")
