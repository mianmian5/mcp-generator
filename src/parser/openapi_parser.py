"""Parse OpenAPI 3.x / Swagger 2.0 specs into a structured representation ready for code generation."""

import json
import re
from pathlib import Path

import yaml
import prance


def parse_openapi(spec_path: str) -> dict:
    """Parse an OpenAPI/Swagger spec file and return a normalized structure.

    Returns a dict with keys:
        title, version, base_url, description, tools
    Each tool is: {name, description, method, path, path_params, query_params, request_body, response_type}
    """
    spec = _load_spec(spec_path)

    info = spec.get("info", {})
    title = info.get("title", "API")
    version = info.get("version", "1.0.0")
    description = info.get("description", "")

    base_url = _extract_base_url(spec)

    tools = []
    for path_str, path_item in spec.get("paths", {}).items():
        for method in ["get", "post", "put", "delete", "patch", "options", "head"]:
            operation = path_item.get(method)
            if operation is None:
                continue
            tool = _extract_tool(path_str, method, operation, spec)
            tools.append(tool)

    return {
        "title": title,
        "version": version,
        "description": description,
        "base_url": base_url,
        "tools": tools,
    }


def _load_spec(spec_path: str) -> dict:
    path = Path(spec_path)
    raw = path.read_text(encoding="utf-8")

    if path.suffix in (".yaml", ".yml"):
        spec = yaml.safe_load(raw)
    else:
        spec = json.loads(raw)

    # Resolve $ref references using prance
    parser = prance.ResolvingParser(str(path), strict=False)
    parser.parse()
    return parser.specification


def _extract_base_url(spec: dict) -> str:
    servers = spec.get("servers", [])
    if servers:
        return servers[0].get("url", "http://localhost:8000")

    # Swagger 2.0 fallback
    host = spec.get("host", "localhost:8000")
    base_path = spec.get("basePath", "")
    schemes = spec.get("schemes", ["http"])
    return f"{schemes[0]}://{host}{base_path}"


def _extract_tool(path_str: str, method: str, operation: dict, spec: dict) -> dict:
    operation_id = operation.get("operationId", "")
    summary = operation.get("summary", "")
    description = operation.get("description", summary)

    name = operation_id or _generate_tool_name(method, path_str)

    path_params, query_params = _extract_params(operation, spec)

    request_body = _extract_request_body(operation, spec)

    response_type = _extract_response_type(operation, spec)

    return {
        "name": _sanitize_name(name),
        "description": description or name,
        "method": method.upper(),
        "path": path_str,
        "path_params": path_params,
        "query_params": query_params,
        "request_body": request_body,
        "response_type": response_type,
    }


def _extract_params(operation: dict, spec: dict) -> tuple[list[dict], list[dict]]:
    path_params = []
    query_params = []

    for param in operation.get("parameters", []):
        # Resolve $ref if needed
        if "$ref" in param:
            param = _resolve_ref(param["$ref"], spec)

        param_info = {
            "name": param.get("name", ""),
            "description": param.get("description", ""),
            "required": param.get("required", False),
            "schema": param.get("schema", {"type": "string"}),
        }

        if param.get("in") == "path":
            path_params.append(param_info)
        elif param.get("in") == "query":
            query_params.append(param_info)

    return path_params, query_params


def _extract_request_body(operation: dict, spec: dict) -> dict | None:
    body = operation.get("requestBody")
    if body is None:
        return None

    if "$ref" in body:
        body = _resolve_ref(body["$ref"], spec)

    content = body.get("content", {})
    json_content = content.get("application/json", {})
    schema = json_content.get("schema", {})

    return {
        "description": body.get("description", ""),
        "required": body.get("required", False),
        "schema": schema,
    }


def _extract_response_type(operation: dict, spec: dict) -> str:
    responses = operation.get("responses", {})
    success = responses.get("200") or responses.get("201") or responses.get("2XX")
    if success is None:
        for code in responses:
            if code.startswith("2"):
                success = responses[code]
                break

    if success is None:
        return "dict"

    if "$ref" in success:
        success = _resolve_ref(success["$ref"], spec)

    content = success.get("content", {})
    json_content = content.get("application/json", {})
    schema = json_content.get("schema", {})

    if not schema:
        return "dict"

    schema_type = schema.get("type", "object")
    if schema_type == "array":
        items = schema.get("items", {})
        ref = items.get("$ref", "")
        if ref:
            return _ref_name(ref)
        return f"list[{items.get('type', 'dict')}]"

    return schema_type


def _resolve_ref(ref: str, spec: dict) -> dict:
    """Resolve a JSON $ref pointer within the spec."""
    parts = ref.lstrip("#/").split("/")
    current = spec
    for part in parts:
        current = current.get(part, {})
    return current


def _generate_tool_name(method: str, path_str: str) -> str:
    """Generate a readable tool name from HTTP method and path."""
    # Replace path params with descriptive segments
    clean = re.sub(r"\{(\w+)}", r"by_\1", path_str)
    # Split on non-alphanumeric
    parts = re.split(r"[^a-zA-Z0-9]+", clean.strip("/"))
    parts = [p for p in parts if p]
    return f"{method}_{'_'.join(parts)}"


def _sanitize_name(name: str) -> str:
    """Make a string safe for use as a Python function name."""
    # Replace non-alphanumeric with underscore
    name = re.sub(r"[^a-zA-Z0-9_]", "_", name)
    # Remove leading digits
    if name and name[0].isdigit():
        name = "_" + name
    # Collapse multiple underscores
    name = re.sub(r"_+", "_", name)
    return name.lower().strip("_")


def _ref_name(ref: str) -> str:
    """Extract the schema name from a $ref."""
    return ref.split("/")[-1]
