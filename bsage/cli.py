"""BSage CLI — client for the BSage Gateway."""

from __future__ import annotations

import re

import click
import httpx
import uvicorn

from bsage.core.config import get_settings
from bsage.garden.vault import Vault


def _validate_skill_name(name: str) -> str:
    """Validate a skill name matches the required pattern."""
    if not re.match(r"^[a-z][a-z0-9-]*$", name):
        msg = f"Invalid skill name: {name}. Use lowercase alphanumeric with hyphens."
        raise click.BadParameter(msg)
    return name


@click.group()
def main() -> None:
    """BSage — Personal AI Agent for your 2nd Brain."""


@main.command()
def run() -> None:
    """Start the BSage Gateway server."""
    settings = get_settings()
    click.echo(f"Starting BSage Gateway on {settings.gateway_host}:{settings.gateway_port}")
    uvicorn.run(
        "bsage.gateway.app:create_app",
        factory=True,
        host=settings.gateway_host,
        port=settings.gateway_port,
        log_level=settings.log_level,
    )


@main.command()
def init() -> None:
    """Initialize the Vault directory structure."""
    settings = get_settings()
    vault = Vault(settings.vault_path)
    vault.ensure_dirs()
    click.echo(f"Vault initialized at {settings.vault_path}")


@main.command()
@click.option("--host", default=None, help="Gateway host")
@click.option("--port", default=None, type=int, help="Gateway port")
def skills(host: str | None, port: int | None) -> None:
    """List all loaded skills from the Gateway."""
    settings = get_settings()
    base_url = f"http://{host or settings.gateway_host}:{port or settings.gateway_port}"

    try:
        response = httpx.get(f"{base_url}/api/skills", timeout=5.0)
        response.raise_for_status()
    except httpx.ConnectError:
        click.echo("Error: Cannot connect to Gateway. Is it running?", err=True)
        raise SystemExit(1) from None

    data = response.json()
    if not data:
        click.echo("No skills loaded.")
        return

    click.echo(f"{'Name':<25} {'Category':<12} {'Dangerous':<10} Description")
    click.echo("-" * 80)
    for skill in data:
        danger = "YES" if skill["is_dangerous"] else "no"
        desc = skill["description"]
        click.echo(f"{skill['name']:<25} {skill['category']:<12} {danger:<10} {desc}")


@main.command("run-skill")
@click.argument("name")
@click.option("--host", default=None, help="Gateway host")
@click.option("--port", default=None, type=int, help="Gateway port")
def run_skill(name: str, host: str | None, port: int | None) -> None:
    """Run a specific skill by name."""
    _validate_skill_name(name)
    settings = get_settings()
    base_url = f"http://{host or settings.gateway_host}:{port or settings.gateway_port}"

    try:
        response = httpx.post(f"{base_url}/api/skills/{name}/run", timeout=30.0)
        response.raise_for_status()
    except httpx.ConnectError:
        click.echo("Error: Cannot connect to Gateway. Is it running?", err=True)
        raise SystemExit(1) from None
    except httpx.HTTPStatusError as exc:
        click.echo(f"Error: {exc.response.json().get('detail', 'Unknown error')}", err=True)
        raise SystemExit(1) from None

    data = response.json()
    click.echo(f"Skill '{name}' executed successfully.")
    click.echo(f"Results: {data.get('results', [])}")


@main.command()
@click.option("--host", default=None, help="Gateway host")
@click.option("--port", default=None, type=int, help="Gateway port")
def health(host: str | None, port: int | None) -> None:
    """Check Gateway health status."""
    settings = get_settings()
    base_url = f"http://{host or settings.gateway_host}:{port or settings.gateway_port}"

    try:
        response = httpx.get(f"{base_url}/api/health", timeout=5.0)
        response.raise_for_status()
    except httpx.ConnectError:
        click.echo("Error: Cannot connect to Gateway. Is it running?", err=True)
        raise SystemExit(1) from None

    data = response.json()
    click.echo(f"Gateway status: {data.get('status', 'unknown')}")
