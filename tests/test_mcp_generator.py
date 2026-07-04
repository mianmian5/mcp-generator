"""Tests for MCP code generator."""

import ast
import tempfile
import os
import pytest
from src.generator.mcp_generator import generate_from_openapi, generate_from_database


class TestGenerateFromOpenAPI:
    def test_generates_valid_python(self):
        spec = {
            "title": "TestAPI",
            "version": "1.0",
            "description": "Test",
            "base_url": "http://localhost:8000",
            "tools": [
                {
                    "name": "get_items",
                    "description": "Get all items",
                    "method": "GET",
                    "path": "/items",
                    "path_params": [],
                    "query_params": [
                        {"name": "limit", "type": "integer", "required": False, "schema": {"type": "integer"}}
                    ],
                    "request_body": None,
                    "response_type": "array",
                }
            ],
        }
        code = generate_from_openapi(spec)
        ast.parse(code)  # must be valid Python

    def test_generates_server_name(self):
        spec = {
            "title": "TestAPI",
            "version": "1.0",
            "description": "",
            "base_url": "http://localhost:8000",
            "tools": [],
        }
        code = generate_from_openapi(spec)
        assert 'Server("testapi")' in code
        assert "TESTAPI_BASE_URL" in code

    def test_generates_header_api_key_env(self):
        spec = {
            "title": "Xquik API",
            "version": "1.0",
            "description": "",
            "base_url": "https://xquik.com",
            "security_schemes": {
                "apiKey": {"type": "apiKey", "in": "header", "name": "x-api-key"}
            },
            "tools": [],
        }
        code = generate_from_openapi(spec)
        assert 'h["x-api-key"] = os.environ["APIKEY"]' in code
        assert 'export APIKEY="your-api-key"  # sends x-api-key' in code

    def test_outputs_to_file(self):
        spec = {
            "title": "FileTest",
            "version": "1.0",
            "description": "",
            "base_url": "http://localhost:8000",
            "tools": [],
        }
        path = os.path.join(tempfile.gettempdir(), "test_output.py")
        generate_from_openapi(spec, path)
        content = open(path).read()
        assert "FileTest" in content
        ast.parse(content)  # must be valid syntax


class TestGenerateFromDatabase:
    def test_generates_valid_python_sqlite(self):
        spec = {
            "db_type": "sqlite",
            "connection_string": "sqlite:///test.db",
            "tables": [
                {"name": "users", "columns": [], "row_count": 0},
            ],
        }
        code = generate_from_database(spec)
        ast.parse(code)

    def test_includes_table_tools(self):
        spec = {
            "db_type": "sqlite",
            "connection_string": "sqlite:///test.db",
            "tables": [
                {"name": "users", "columns": [{"name": "id", "type": "INTEGER"}], "row_count": 10},
                {"name": "orders", "columns": [{"name": "id", "type": "INTEGER"}], "row_count": 5},
            ],
        }
        code = generate_from_database(spec)
        assert "describe_users" in code
        assert "sample_users" in code
        assert "describe_orders" in code
        assert "sample_orders" in code
        assert "list_tables" in code
        assert "run_query" in code

    def test_read_only_check_in_output(self):
        spec = {
            "db_type": "sqlite",
            "connection_string": "sqlite:///test.db",
            "tables": [],
        }
        code = generate_from_database(spec)
        assert "read-only" in code.lower() or "SELECT" in code
