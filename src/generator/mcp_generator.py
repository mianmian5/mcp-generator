"""Generate complete, runnable MCP server code from parsed specifications."""

from pathlib import Path
from jinja2 import Environment, FileSystemLoader


TEMPLATE_DIR = Path(__file__).parent.parent.parent / "templates"


def generate_from_openapi(spec: dict, output_path: str | None = None) -> str:
    """Generate a Python MCP server from a parsed OpenAPI spec."""
    env = Environment(
        loader=FileSystemLoader(str(TEMPLATE_DIR)),
        trim_blocks=True,
        lstrip_blocks=True,
    )
    template = env.get_template("mcp_server_python.py.j2")

    tools_data = [_prepare_openapi_tool(t) for t in spec["tools"]]

    context = {
        "source_type": "openapi",
        "server_name": _to_module_name(spec["title"]),
        "title": spec["title"],
        "version": spec["version"],
        "description": spec["description"] or f"Auto-generated MCP server for {spec['title']}",
        "base_url": spec["base_url"],
        "env_prefix": _to_env_prefix(spec["title"]),
        "tools": tools_data,
    }

    code = template.render(**context)

    if output_path:
        Path(output_path).write_text(code, encoding="utf-8")

    return code


def generate_from_database(spec: dict, output_path: str | None = None) -> str:
    """Generate a Python MCP server from a parsed database schema."""
    env = Environment(
        loader=FileSystemLoader(str(TEMPLATE_DIR)),
        trim_blocks=True,
        lstrip_blocks=True,
    )
    template = env.get_template("mcp_server_db_python.py.j2")

    context = {
        "server_name": f"{spec['db_type']}_mcp_server",
        "db_type": spec["db_type"],
        "connection_string": spec["connection_string"],
        "tables": spec["tables"],
    }

    code = template.render(**context)

    if output_path:
        Path(output_path).write_text(code, encoding="utf-8")

    return code


def _prepare_openapi_tool(tool: dict) -> dict:
    """Prepare a single tool for template rendering. Pre-computes all code snippets."""
    # Build function params with types and defaults
    params = []
    fn_signature_parts = []
    for p in tool["path_params"]:
        py_type = _python_type(p["schema"].get("type", "string"))
        params.append({"name": p["name"], "annotation": py_type, "default": None})
        fn_signature_parts.append(f"{p['name']}: {py_type}")
    for p in tool["query_params"]:
        py_type = _python_type(p["schema"].get("type", "string"))
        if p["required"]:
            params.append({"name": p["name"], "annotation": py_type, "default": None})
            fn_signature_parts.append(f"{p['name']}: {py_type}")
        else:
            default_val = _default_value(p["schema"])
            params.append({"name": p["name"], "annotation": py_type, "default": default_val})
            fn_signature_parts.append(f"{p['name']}: {py_type} = {default_val}")
    if tool["request_body"]:
        if tool["request_body"]["required"]:
            params.append({"name": "body", "annotation": "dict", "default": None})
            fn_signature_parts.append("body: dict")
        else:
            params.append({"name": "body", "annotation": "dict | None", "default": "None"})
            fn_signature_parts.append("body: dict | None = None")

    url_line = f'f"{{BASE_URL}}{tool["path"]}"'

    # Build query params line
    query_param_names = [p["name"] for p in tool["query_params"]]
    if query_param_names:
        pairs = ", ".join(f'"{n}": {n}' for n in query_param_names)
        query_line = f"params={{k: v for k, v in {{{pairs}}}.items() if v is not None}}"
    else:
        query_line = ""

    # Build request body line
    has_body = bool(tool["request_body"])
    if has_body:
        body_line = "json=body"
    else:
        body_line = ""

    # Build client call arguments
    call_args = [url_line]
    if has_body:
        call_args.append(body_line)
    if query_line:
        call_args.append(query_line)
    call_args.append("headers=_headers()")
    call_args_str = ",\n            ".join(call_args)

    return {
        **tool,
        "params": params,
        "fn_signature": ", ".join(fn_signature_parts),
        "call_args": call_args_str,
        "method_lower": tool["method"].lower(),
    }


def _to_module_name(title: str) -> str:
    return "".join(c if c.isalnum() else "_" for c in title).lower().strip("_") or "api"


def _to_env_prefix(title: str) -> str:
    return "".join(c.upper() if c.isalnum() else "_" for c in title).strip("_") or "API"


def _python_type(openapi_type: str) -> str:
    mapping = {
        "string": "str",
        "integer": "int",
        "number": "float",
        "boolean": "bool",
        "array": "list",
        "object": "dict",
    }
    return mapping.get(openapi_type, "str")


def _default_value(schema: dict) -> str:
    t = schema.get("type", "string")
    defaults = {"string": '""', "integer": "0", "number": "0.0", "boolean": "False", "array": "[]"}
    return defaults.get(t, "None")
