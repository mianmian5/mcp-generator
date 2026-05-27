"""CLI entry point for MCP Generator."""

import sys
from pathlib import Path

import click

from src.parser import parse_openapi, parse_database
from src.generator import generate_from_openapi, generate_from_database


@click.group()
@click.version_option(version="0.1.0")
def cli():
    """MCP Generator - Auto-generate MCP servers from OpenAPI specs or database schemas."""


@cli.command()
@click.argument("spec_path", type=click.Path(exists=True))
@click.option(
    "-o", "--output",
    default=None,
    help="Output file path. Defaults to <spec_name>_mcp_server.py",
)
@click.option(
    "-n", "--name",
    default=None,
    help="Custom server name (default: derived from spec title).",
)
def generate(spec_path: str, output: str | None, name: str | None):
    """Generate an MCP server from an OpenAPI spec file.

    SPEC_PATH: Path to an OpenAPI 3.x or Swagger 2.0 JSON/YAML file.
    """
    click.echo(f"Parsing OpenAPI spec: {spec_path}")
    try:
        spec = parse_openapi(spec_path)
    except Exception as e:
        click.echo(f"Error parsing spec: {e}", err=True)
        sys.exit(1)

    if name:
        spec["title"] = name

    if output is None:
        input_path = Path(spec_path)
        output = str(input_path.with_suffix("").with_suffix("")) + "_mcp_server.py"

    click.echo(f"Found {len(spec['tools'])} API endpoints")
    for tool in spec["tools"]:
        click.echo(f"  {tool['method']:6} {tool['path']} -> {tool['name']}()")

    try:
        generate_from_openapi(spec, output)
    except Exception as e:
        click.echo(f"Error generating server: {e}", err=True)
        sys.exit(1)

    click.echo(f"\nGenerated MCP server: {output}")
    click.echo(f"Usage: python {output}")


@cli.command()
@click.argument("connection_string")
@click.option(
    "-o", "--output",
    default=None,
    help="Output file path. Defaults to <db_type>_mcp_server.py",
)
def from_db(connection_string: str, output: str | None):
    """Generate an MCP server from a database schema.

    CONNECTION_STRING: Database URL (sqlite:///path/to/db, postgresql://..., mysql://...)
    """
    click.echo(f"Connecting to database: {connection_string}")
    try:
        spec = parse_database(connection_string)
    except Exception as e:
        click.echo(f"Error parsing database: {e}", err=True)
        sys.exit(1)

    if output is None:
        output = f"{spec['db_type']}_mcp_server.py"

    click.echo(f"Found {len(spec['tables'])} tables:")
    for table in spec["tables"]:
        cols = ", ".join(c["name"] for c in table["columns"][:4])
        more = "..." if len(table["columns"]) > 4 else ""
        click.echo(f"  {table['name']} ({table['row_count']} rows) [{cols}{more}]")

    try:
        generate_from_database(spec, output)
    except Exception as e:
        click.echo(f"Error generating server: {e}", err=True)
        sys.exit(1)

    click.echo(f"\nGenerated MCP server: {output}")
    click.echo(f"Usage: python {output}")


if __name__ == "__main__":
    cli()
