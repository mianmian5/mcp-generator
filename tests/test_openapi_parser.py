"""Tests for OpenAPI parser."""

import pytest
from src.parser.openapi_parser import parse_openapi

FIXTURE = "tests/fixtures/petstore.yaml"
XQUIK_FIXTURE = "tests/fixtures/xquik.yaml"


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

    def test_xquik_openapi31_api_key_security(self):
        result = parse_openapi(XQUIK_FIXTURE)

        assert result["title"] == "Xquik API"
        assert result["base_url"] == "https://xquik.com"
        assert result["security_schemes"]["apiKey"]["name"] == "x-api-key"
        assert result["security"] == [{"apiKey": []}]

    def test_xquik_query_params_and_request_body(self):
        result = parse_openapi(XQUIK_FIXTURE)

        search = next(t for t in result["tools"] if t["name"] == "searchtweets")
        assert search["method"] == "GET"
        assert [p["name"] for p in search["query_params"]] == ["q", "limit"]
        assert search["query_params"][0]["required"] is True

        webhook = next(t for t in result["tools"] if t["name"] == "createwebhook")
        assert webhook["method"] == "POST"
        assert webhook["request_body"]["required"] is True
        assert webhook["request_body"]["schema"]["required"] == ["url"]
