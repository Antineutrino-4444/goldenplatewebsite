"""Drop the obsolete kv_store table from the database.

This script removes the kv_store table which is no longer used after refactoring
to store all data directly in relational database tables.
"""
import os
from sqlalchemy import create_engine, inspect, text

DATABASE_URL = os.environ.get('DATABASE_URL', 'sqlite:///data/golden_plate_recorder.db')

# Configure SQLite-specific settings
connect_args = {}
if DATABASE_URL.startswith('sqlite'):
    connect_args = {
        'check_same_thread': False,
        'timeout': 30,
    }

engine = create_engine(
    DATABASE_URL,
    connect_args=connect_args,
    pool_pre_ping=True,
)


def drop_kv_store_table():
    """Drop the kv_store table if it exists."""
    inspector = inspect(engine)
    
    if 'kv_store' in inspector.get_table_names():
        print("Dropping kv_store table...")
        with engine.begin() as conn:
            conn.execute(text("DROP TABLE kv_store"))
        print("✓ kv_store table dropped successfully")
    else:
        print("ℹ kv_store table does not exist (already removed or never created)")


if __name__ == "__main__":
    drop_kv_store_table()
