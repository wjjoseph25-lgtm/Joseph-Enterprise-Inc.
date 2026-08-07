import asyncio

from app.mcp_server import mcp


def test_mcp_publishes_calculate_chart_tool():
    tools = asyncio.run(mcp.list_tools())
    tool_names = {tool.name for tool in tools}

    assert "calculate_chart" in tool_names
    assert "calculate_horary_chart" not in tool_names
