"""
MCP transport setup — stdio and Streamable HTTP.

Provides helpers to run a FastMCP server with the chosen transport.
"""

from __future__ import annotations

import logging
from typing import Any

from mcp.server.fastmcp import FastMCP

logger = logging.getLogger("tgbot2mcp.mcp.transport")


async def run_mcp_server(
    mcp: FastMCP,
    transport: str = "stdio",
    host: str = "127.0.0.1",
    port: int = 8080,
) -> None:
    """
    Run a FastMCP server with the specified transport.

    Args:
        mcp: The FastMCP server instance.
        transport: "stdio" or "http" (Streamable HTTP).
        host: Host for HTTP transport (default: 127.0.0.1).
        port: Port for HTTP transport (default: 8080).
    """
    if transport == "http":
        logger.info(f"Starting MCP server on http://{host}:{port}")
        await mcp.run_async(transport="streamable-http", host=host, port=port)
    else:
        logger.info("Starting MCP server on stdio")
        await mcp.run_async(transport="stdio")
