#!/usr/bin/env python
"""Drop the old subscriptions_alert_type_check constraint."""

from sqlalchemy import text
from src.database import init_db, get_db_session
from src.config import DATABASE_URL

print("Initializing database connection...")
init_db(DATABASE_URL)

sql_statements = [
    "ALTER TABLE subscriptions DROP CONSTRAINT IF EXISTS subscriptions_alert_type_check;",
    "ALTER TABLE reports_sent DROP CONSTRAINT IF EXISTS reports_alert_type_check;",
]

print("Dropping old constraints...")
with get_db_session() as session:
    for sql in sql_statements:
        session.execute(text(sql))
        print(f"✓ Executed: {sql}")
    session.commit()

print("\n✓ Old constraints dropped successfully!")

# Verify
check_constraint_sql = """
SELECT constraint_name 
FROM information_schema.table_constraints 
WHERE table_name='subscriptions' 
AND constraint_type='CHECK'
ORDER BY constraint_name;
"""

print("\nRemaining CHECK constraints on subscriptions table:")
with get_db_session() as session:
    result = session.execute(text(check_constraint_sql))
    for row in result:
        print(f"  - {row[0]}")
