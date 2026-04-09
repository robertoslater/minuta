"""CLI entry point for Minuta."""

from __future__ import annotations

import subprocess
import sys
import webbrowser

import click


@click.group()
def cli():
    """Minuta - Meeting Transcription & Summarization"""
    pass


@cli.command()
@click.option("--host", default="127.0.0.1", help="Backend host")
@click.option("--port", default=8741, help="Backend port")
def start(host: str, port: int):
    """Start the Minuta backend server."""
    import uvicorn
    from minuta.server.app import create_app

    click.echo(f"Starting Minuta on {host}:{port}")
    app = create_app()
    uvicorn.run(app, host=host, port=port, log_level="info")


@cli.command()
def dashboard():
    """Open the dashboard in the browser."""
    webbrowser.open("http://localhost:3000")
    click.echo("Dashboard opened in browser.")


@cli.command()
def status():
    """Check if Minuta is running."""
    import httpx
    try:
        r = httpx.get("http://127.0.0.1:8741/api/health", timeout=3)
        data = r.json()
        click.echo(f"Status: {data['status']}")
        click.echo(f"Uptime: {data['uptime_seconds']}s")
        click.echo(f"Model: {data['transcription_model']}")
        click.echo(f"Provider: {data['summarization_provider']}")
    except Exception:
        click.echo("Minuta is not running.", err=True)
        sys.exit(1)


@cli.command()
def config():
    """Open the config file in $EDITOR."""
    from pathlib import Path
    import os
    config_path = Path.home() / ".minuta" / "config.toml"
    editor = os.environ.get("EDITOR", "nano")
    if not config_path.exists():
        click.echo(f"Config not found at {config_path}. Run 'make install-config' first.")
        sys.exit(1)
    subprocess.run([editor, str(config_path)])
