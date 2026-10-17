"""Compatibilidad con el SDK de MCP v1.x (FastMCP) y v2.x (MCPServer)."""

try:  # SDK v2
    from mcp.server.mcpserver import MCPServer
    from mcp.server.mcpserver.utilities.types import Image as MCPImage
except ImportError:  # SDK v1.x
    from mcp.server.fastmcp import FastMCP as MCPServer  # type: ignore[assignment]
    from mcp.server.fastmcp.utilities.types import Image as MCPImage  # type: ignore[assignment]

__all__ = ["MCPServer", "MCPImage"]
