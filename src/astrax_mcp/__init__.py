"""Astrax - Agentic System Telemetry, Realtime Automation & X-control."""

__version__ = "0.3.0"


def main() -> None:
    """Punto de entrada del servidor MCP (comando `astrax-mcp`)."""
    from .server import run

    run()
