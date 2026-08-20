#!/usr/bin/env python
"""Check if migration 004 has been applied."""

from sqlalchemy import text
from src.database import init_db, get_db_session
from src.config import DATABASE_URL

print("Initializing database connection...")
init_db(DATABASE_URL)

# Query to check constraints
check_constraint_sql = """
SELECT constraint_name 
FROM information_schema.table_constraints 
WHERE table_name='subscriptions' 
AND constraint_type='CHECK'
ORDER BY constraint_name;
"""

print("\nCurrent CHECK constraints on subscriptions table:")
with get_db_session() as session:
    result = session.execute(text(check_constraint_sql))
    for row in result:
        print(f"  - {row[0]}")

# Now run the migration
print("\n\nApplying migration 004...")
sql_statements = [
    "ALTER TABLE subscriptions DROP CONSTRAINT IF EXISTS check_alert_type;",
    "ALTER TABLE subscriptions ADD CONSTRAINT check_alert_type CHECK (alert_type IN ('weekly_alerts', 'monthly_built_area', 'reporte_paramos'));",
    "ALTER TABLE reports_sent DROP CONSTRAINT IF EXISTS check_alert_type_reports;",
    "ALTER TABLE reports_sent ADD CONSTRAINT check_alert_type_reports CHECK (alert_type IN ('weekly_alerts', 'monthly_built_area', 'reporte_paramos'));",
]

with get_db_session() as session:
    for sql in sql_statements:
        session.execute(text(sql))
        print(f"✓ Executed: {sql[:70]}...")
    session.commit()

print("\n✓ Migration applied successfully!")

# Verify the constraints were updated
print("\nVerifying new CHECK constraints:")
with get_db_session() as session:
    result = session.execute(text(check_constraint_sql))
    for row in result:
        print(f"  - {row[0]}")
