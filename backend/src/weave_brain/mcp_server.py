import asyncio
import json
from typing import Any

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import (
    CallToolResult,
    ListToolsResult,
    TextContent,
    Tool,
)

from weave_brain.agent.mapper import tool_result_to_graph_view
from weave_brain.agent.tools import ToolNotFoundError, call_tool

try:
    from weave_brain.core.config import get_settings
except ImportError:
    get_settings = dict  # fallback if Dev C core.config not yet implemented

__all__ = [
    "ToolNotFoundError",
    "app",
    "call_tool",
    "get_settings",
    "handle_tool",
    "list_tools",
    "tool_result_to_graph_view",
]

app = Server("weave-brain")


@app.list_tools()
async def list_tools() -> ListToolsResult:
    return ListToolsResult(
        tools=[
            Tool(
                name="ask_weave",
                description=(
                    "Ask WEAVE a question about the engineering organization. "
                    "Returns a grounded answer backed by knowledge graph data."
                ),
                inputSchema={
                    "type": "object",
                    "properties": {
                        "question": {"type": "string"},
                        "service_id": {
                            "type": "string",
                            "description": "e.g. service:authentication-api",
                        },
                    },
                    "required": ["question"],
                },
            ),
            Tool(
                name="get_service_graph",
                description="Get the knowledge graph for a specific service.",
                inputSchema={
                    "type": "object",
                    "properties": {"service_id": {"type": "string"}},
                    "required": ["service_id"],
                },
            ),
            Tool(
                name="find_experts",
                description="Find engineers who know about a service.",
                inputSchema={
                    "type": "object",
                    "properties": {"service_id": {"type": "string"}},
                    "required": ["service_id"],
                },
            ),
        ]
    )


@app.call_tool()
async def handle_tool(name: str, arguments: dict[str, Any]) -> CallToolResult:
    try:
        if name == "ask_weave":
            from weave_brain.agent.orchestrator import process_question
            from weave_brain.domain.models import ChatRequest

            r = process_question(ChatRequest(question=arguments["question"]))
            return CallToolResult(content=[TextContent(type="text", text=r.answer)])
        elif name in ("get_service_graph", "find_experts"):
            tool_map = {
                "get_service_graph": "get_service_overview",
                "find_experts": "find_experts",
            }
            result = call_tool(tool_map[name], {"service_id": arguments["service_id"]})
            return CallToolResult(
                content=[
                    TextContent(
                        type="text",
                        text=json.dumps(result, indent=2, default=str),
                    )
                ]
            )
        else:
            return CallToolResult(
                content=[TextContent(type="text", text=f"Unknown tool: {name}")]
            )
    except Exception as e:  # noqa: BLE001
        return CallToolResult(
            content=[TextContent(type="text", text=f"Error: {e}")],
            isError=True,
        )


if __name__ == "__main__":

    async def main() -> None:
        async with stdio_server() as streams:
            await app.run(streams[0], streams[1], app.create_initialization_options())

    asyncio.run(main())
