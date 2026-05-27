"""Tests for OpenAPI parser."""

import pytest
from src.parser.openapi_parser import parse_openapi

FIXTURE = "tests/fixtures/petstore.yaml"


class TestParseOpenAPI:
    def test_parses_title_and_version(self):
        result = parse_openapi(FIXTURE)
        assert result["title"] == "Petstore API"
        assert result["version"] == "1.0.0"

    def test_finds_all_tools(self):
        result = parse_openapi(FIXTURE)
        tool_names = [t["name"] for t in result["tools"]]
        assert "listpets" in tool_names
        assert "createpet" in tool_names
        assert "getpet" in tool_names
        assert "deletepet" in tool_names
        assert "searchpets" in tool_names
        assert len(result["tools"]) == 5

    def test_tool_has_required_fields(self):
        result = parse_openapi(FIXTURE)
        for tool in result["tools"]:
            assert "name" in tool
            assert "method" in tool
            assert "path" in tool
            assert "description" in tool

    def test_path_params_extracted(self):
        result = parse_openapi(FIXTURE)
        get_pet = next(t for t in result["tools"] if t["name"] == "getpet")
        assert any(p["name"] == "petId" and p["required"] for p in get_pet["path_params"])

    def test_query_params_extracted(self):
        result = parse_openapi(FIXTURE)
        list_pets = next(t for t in result["tools"] if t["name"] == "listpets")
        assert any(p["name"] == "limit" for p in list_pets["query_params"])

    def test_extracts_base_url(self):
        result = parse_openapi(FIXTURE)
        assert result["base_url"].startswith("http")

    def test_generated_tool_names_are_valid_python(self):
        result = parse_openapi(FIXTURE)
        for tool in result["tools"]:
            assert tool["name"].isidentifier()
