"""Oracle Database connection and query helpers."""

import oracledb
from flask import g, current_app
import os


def get_db():
    """Get a database connection for the current request."""
    db = g.get("db")
    if db is None:
        db = oracledb.connect(
            user=os.getenv("ORACLE_USER"),
            password=os.getenv("ORACLE_PASSWORD"),
            dsn=os.getenv("ORACLE_DSN", "localhost:1521/XEPDB1"),
        )
        db.autocommit = False
        g.db = db
    return g.db


def close_db(e=None):
    """Close the database connection at end of request."""
    db = g.pop("db", None)
    if db is not None:
        try:
            db.close()
        except Exception:
            pass


def init_db(app):
    """Register DB teardown with Flask app."""
    app.teardown_appcontext(close_db)


def row_to_dict(cursor, row):
    """Convert a single Oracle row to a dictionary using cursor description."""
    if row is None:
        return None
    columns = [col[0].lower() for col in cursor.description]
    return dict(zip(columns, row))


def rows_to_dicts(cursor, rows):
    """Convert multiple Oracle rows to a list of dictionaries."""
    if not rows:
        return []
    columns = [col[0].lower() for col in cursor.description]
    return [dict(zip(columns, row)) for row in rows]


def fetch_one(cursor, query, params=None):
    """Execute query and return single row as dict."""
    cursor.execute(query, params or {})
    row = cursor.fetchone()
    return row_to_dict(cursor, row)


def fetch_all(cursor, query, params=None):
    """Execute query and return all rows as list of dicts."""
    cursor.execute(query, params or {})
    rows = cursor.fetchall()
    return rows_to_dicts(cursor, rows)


def execute_insert(cursor, query, params=None):
    """Execute an INSERT and return the rowid or None."""
    cursor.execute(query, params or {})


def run_sql_file(cursor, filepath):
    """Run a SQL file, splitting on semicolons."""
    import os
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    full_path = os.path.join(base, filepath)
    with open(full_path, "r") as f:
        sql = f.read()
    # Split on ; but be careful with PL/SQL blocks
    statements = []
    current = ""
    in_plsql = False
    for line in sql.split("\n"):
        stripped = line.strip().upper()
        if "BEGIN" in stripped or "CREATE" in stripped and "PROCEDURE" in stripped or "CREATE" in stripped and "FUNCTION" in stripped or "CREATE" in stripped and "TRIGGER" in stripped:
            in_plsql = True
        current += line + "\n"
        if stripped == "/" and in_plsql:
            statements.append(current.strip())
            current = ""
            in_plsql = False
        elif stripped.endswith(";") and not in_plsql:
            statements.append(current.strip())
            current = ""
    if current.strip():
        statements.append(current.strip())

    for stmt in statements:
        if stmt and not stmt.startswith("--"):
            try:
                cursor.execute(stmt)
            except oracledb.DatabaseError:
                # Table already exists etc.
                pass
