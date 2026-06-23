from __future__ import annotations

import json
import logging
import sys
from typing import Any

from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

from providers.llm.base import ToolDefinition, ToolResult

logger = logging.getLogger(__name__)


class AgentMCPClient:
    """Wraps an MCP ClientSession over stdio transport.

    Starts a FastMCP server as a subprocess, provides list_tools() and
    call_tool() that convert between MCP protocol types and our internal
    ToolDefinition / ToolResult dataclasses.
    """

    def __init__(self) -> None:
        self._session: ClientSession | None = None
        self._cm: Any = None
        self._session_cm: Any = None

    async def connect(
        self,
        server_script: str,
        env: dict[str, str] | None = None,
    ) -> None:
        params = StdioServerParameters(
            command=sys.executable,
            args=[server_script],
            env=env,
        )
        self._cm = stdio_client(params)
        read_stream, write_stream = await self._cm.__aenter__()
        self._session_cm = ClientSession(read_stream, write_stream)
        self._session = await self._session_cm.__aenter__()
        await self._session.initialize()
        logger.info("MCP client connected to %s", server_script)

    async def list_tools(self) -> list[ToolDefinition]:
        if not self._session:
            raise RuntimeError("MCP client not connected")
        result = await self._session.list_tools()
        tools = []
        for t in result.tools:
            tools.append(
                ToolDefinition(
                    name=t.name,
                    description=t.description or "",
                    input_schema=t.inputSchema,
                )
            )
        return tools

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> str:
        if not self._session:
            raise RuntimeError("MCP client not connected")
        result = await self._session.call_tool(name, arguments)
        parts = []
        for block in result.content:
            if hasattr(block, "text"):
                parts.append(block.text)
            else:
                parts.append(str(block))
        content = "\n".join(parts) if parts else ""
        if result.isError:
            raise RuntimeError(content)
        return content

    async def disconnect(self) -> None:
        if self._session_cm:
            await self._session_cm.__aexit__(None, None, None)
            self._session = None
        if self._cm:
            await self._cm.__aexit__(None, None, None)
            self._cm = None
        logger.info("MCP client disconnected")
