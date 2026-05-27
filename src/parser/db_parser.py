"""Parse database schemas into a structured representation for MCP server generation.

Supports SQLite, PostgreSQL, and MySQL databases.
"""

from typing import Any


def parse_database(connection_string: str) -> dict:
    """Connect to a database, extract schema info, and return a structured representation.

    Returns a dict with keys:
        db_type, tables, connection_string
    Each table is: {name, columns, row_count}
    Each column is: {name, type, nullable, primary_key, default}
    """
    db_type = _detect_db_type(connection_string)
    tables = _extract_tables(connection_string, db_type)
    return {
        "db_type": db_type,
        "connection_string": connection_string,
        "tables": tables,
    }


def _detect_db_type(connection_string: str) -> str:
    if connection_string.startswith("sqlite://"):
        return "sqlite"
    if connection_string.startswith("postgresql://") or connection_string.startswith("postgres://"):
        return "postgresql"
    if connection_string.startswith("mysql://"):
        return "mysql"
    if connection_string.endswith(".db") or connection_string.endswith(".sqlite"):
        return "sqlite"
    raise ValueError(f"Cannot detect database type from connection string: {connection_string}")


def _extract_tables(connection_string: str, db_type: str) -> list[dict]:
    if db_type == "sqlite":
        return _extract_sqlite(connection_string)
    elif db_type == "postgresql":
        return _extract_postgresql(connection_string)
    elif db_type == "mysql":
        return _extract_mysql(connection_string)
    return []


def _extract_sqlite(connection_string: str) -> list[dict]:
    import sqlite3

    db_path = connection_string.replace("sqlite:///", "").replace("sqlite://", "")
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' AND name NOT LIKE '\\_%'")
    table_names = [row[0] for row in cursor.fetchall()]

    tables = []
    for tname in table_names:
        cursor.execute(f"PRAGMA table_info('{tname}')")
        columns = [
            {
                "name": row["name"],
                "type": row["type"],
                "nullable": not row["notnull"],
                "primary_key": bool(row["pk"]),
                "default": row["dflt_value"],
            }
            for row in cursor.fetchall()
        ]

        cursor.execute(f"SELECT COUNT(*) FROM '{tname}'")
        row_count = cursor.fetchone()[0]

        cursor.execute(f"SELECT * FROM '{tname}' LIMIT 3")
        sample_rows = [dict(row) for row in cursor.fetchall()]

        tables.append({
            "name": tname,
            "columns": columns,
            "row_count": row_count,
            "sample_rows": sample_rows,
        })

    conn.close()
    return tables


def _extract_postgresql(connection_string: str) -> list[dict]:
    try:
        import psycopg2
    except ImportError:
        raise ImportError("psycopg2 is required for PostgreSQL support. pip install psycopg2-binary")

    conn = psycopg2.connect(connection_string)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT table_name FROM information_schema.tables
        WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
        ORDER BY table_name
    """)
    table_names = [row[0] for row in cursor.fetchall()]

    tables = []
    for tname in table_names:
        cursor.execute("""
            SELECT column_name, data_type, is_nullable,
                   column_default,
                   CASE WHEN pk.column_name IS NOT NULL THEN true ELSE false END AS is_pk
            FROM information_schema.columns c
            LEFT JOIN (
                SELECT ku.column_name
                FROM information_schema.table_constraints tc
                JOIN information_schema.key_column_usage ku
                    ON tc.constraint_name = ku.constraint_name
                WHERE tc.constraint_type = 'PRIMARY KEY' AND tc.table_name = %s
            ) pk ON c.column_name = pk.column_name
            WHERE c.table_name = %s
            ORDER BY c.ordinal_position
        """, (tname, tname))
        columns = [
            {
                "name": row[0],
                "type": row[1],
                "nullable": row[2] == "YES",
                "primary_key": row[4],
                "default": str(row[3]) if row[3] else None,
            }
            for row in cursor.fetchall()
        ]

        cursor.execute(f'SELECT COUNT(*) FROM "{tname}"')
        row_count = cursor.fetchone()[0]

        tables.append({
            "name": tname,
            "columns": columns,
            "row_count": row_count,
        })

    conn.close()
    return tables


def _extract_mysql(connection_string: str) -> list[dict]:
    try:
        import pymysql
    except ImportError:
        try:
            import MySQLdb
        except ImportError:
            raise ImportError("pymysql or mysqlclient is required for MySQL support. pip install pymysql")

    conn = pymysql.connect(**parse_mysql_url(connection_string))
    cursor = conn.cursor()

    cursor.execute("SHOW TABLES")
    table_names = [row[0] for row in cursor.fetchall()]

    tables = []
    for tname in table_names:
        cursor.execute(f"DESCRIBE `{tname}`")
        columns = [
            {
                "name": row[0],
                "type": row[1],
                "nullable": row[2] == "YES",
                "primary_key": row[3] == "PRI",
                "default": str(row[4]) if row[4] else None,
            }
            for row in cursor.fetchall()
        ]

        cursor.execute(f"SELECT COUNT(*) FROM `{tname}`")
        row_count = cursor.fetchone()[0]

        tables.append({
            "name": tname,
            "columns": columns,
            "row_count": row_count,
        })

    conn.close()
    return tables


def parse_mysql_url(url: str) -> dict:
    """Parse a mysql://user:pass@host:port/dbname connection string into kwargs for pymysql."""
    from urllib.parse import urlparse, parse_qs

    parsed = urlparse(url)
    params = {
        "host": parsed.hostname or "localhost",
        "port": parsed.port or 3306,
        "user": parsed.username or "root",
        "password": parsed.password or "",
        "database": parsed.path.lstrip("/") if parsed.path else "",
    }
    for key, values in parse_qs(parsed.query).items():
        params[key] = values[0]
    return params
