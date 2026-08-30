"""Database connection and query helpers for Oracle."""

import os
import oracledb
from flask import g

def get_db():
    """Get or create Oracle database connection."""
    if 'db' not in g:
        try:
            # Use connection string
            dsn = oracledb.make_dsn(
                host=os.getenv("ORACLE_DSN", "localhost").split(":")[0],
                port=int(os.getenv("ORACLE_DSN", "localhost:1521").split(":")[1].split("/")[0]) if ":" in os.getenv("ORACLE_DSN", "") else 1521,
                service_name=os.getenv("ORACLE_DSN", "XEPDB1").split("/")[-1]
            )
            
            g.db = oracledb.connect(
                user=os.getenv("ORACLE_USER", ""),
                password=os.getenv("ORACLE_PASSWORD", ""),
                dsn=dsn
            )
        except Exception as e:
            print(f"Database connection failed: {e}")
            return None
    
    return g.db


def close_db(e=None):
    """Close database connection."""
    db = g.pop("db", None)
    if db is not None:
        try:
            db.close()
        except Exception:
            pass


def fetch_one(cursor, query, params=None):
    """Execute query and fetch one row."""
    try:
        cursor.execute(query, params or {})
        return cursor.fetchone()
    except Exception as e:
        print(f"Query error: {e}")
        return None


def fetch_all(cursor, query, params=None):
    """Execute query and fetch all rows."""
    try:
        cursor.execute(query, params or {})
        return cursor.fetchall()
    except Exception as e:
        print(f"Query error: {e}")
        return []


def execute_insert(cursor, query, params=None):
    """Execute insert query and return inserted ID."""
    try:
        cursor.execute(query, params or {})
        cursor.execute("SELECT @@IDENTITY")
        result = cursor.fetchone()
        return result[0] if result else None
    except Exception as e:
        print(f"Insert error: {e}")
        return None


def execute_update(cursor, query, params=None):
    """Execute update query and return rows affected."""
    try:
        cursor.execute(query, params or {})
        return cursor.rowcount
    except Exception as e:
        print(f"Update error: {e}")
        return 0
