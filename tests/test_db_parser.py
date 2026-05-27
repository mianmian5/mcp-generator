"""Tests for database parser."""

import os
import sqlite3
import tempfile
import pytest
from src.parser.db_parser import parse_database, _detect_db_type


class TestDetectDBType:
    def test_detects_sqlite(self):
        assert _detect_db_type("sqlite:///test.db") == "sqlite"
        assert _detect_db_type("test.db") == "sqlite"

    def test_detects_postgresql(self):
        assert _detect_db_type("postgresql://localhost/test") == "postgresql"
        assert _detect_db_type("postgres://localhost/test") == "postgresql"

    def test_detects_mysql(self):
        assert _detect_db_type("mysql://localhost/test") == "mysql"

    def test_raises_on_unknown(self):
        with pytest.raises(ValueError):
            _detect_db_type("oracle://localhost/test")


class TestParseSQLite:
    def test_extracts_tables_and_columns(self):
        path = os.path.join(tempfile.gettempdir(), "test_mcp_pytest.db")
        conn = sqlite3.connect(path)
        conn.execute("CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT)")
        conn.execute("INSERT INTO users VALUES (1, 'Alice')")
        conn.commit()
        conn.close()

        try:
            result = parse_database(f"sqlite:///{path}")
            assert result["db_type"] == "sqlite"
            assert len(result["tables"]) == 1
            table = result["tables"][0]
            assert table["name"] == "users"
            assert table["row_count"] == 1
            col_names = [c["name"] for c in table["columns"]]
            assert "id" in col_names
            assert "name" in col_names
        finally:
            os.unlink(path)

    def test_filters_sqlite_internal_tables(self):
        path = os.path.join(tempfile.gettempdir(), "test_mcp_filter.db")
        conn = sqlite3.connect(path)
        conn.execute("CREATE TABLE my_data (x INTEGER)")
        conn.commit()
        conn.close()

        try:
            result = parse_database(f"sqlite:///{path}")
            table_names = [t["name"] for t in result["tables"]]
            assert "my_data" in table_names
            # sqlite_sequence should not appear (internal table pattern)
            assert not any(t.startswith("sqlite_") for t in table_names)
        finally:
            os.unlink(path)
