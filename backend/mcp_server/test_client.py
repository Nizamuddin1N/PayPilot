"""Proves the MCP server actually speaks the protocol correctly, using the
SDK's own client (not our code) — spawns server.py as a subprocess over
stdio, lists tools, and calls both of them."""

import asyncio
import json
import os
import sys

from mcp import StdioServerParameters
from mcp.client import Client

SERVER_PARAMS = StdioServerParameters(
    command=sys.executable,
    args=[os.path.join(os.path.dirname(__file__), "server.py")],
)


async def main():
    async with Client(SERVER_PARAMS) as client:
        tools = await client.list_tools()
        print("tools:", [t.name for t in tools.tools])

        print("\n--- search_catalog(category=Electronics, max_price_inr=2000) ---")
        result = await client.call_tool("search_catalog", {"category": "Electronics", "max_price_inr": 2000})
        print(json.dumps(json.loads(result.content[0].text), indent=2))

        print("\n--- get_quote(ele-001) ---")
        result = await client.call_tool("get_quote", {"product_id": "ele-001"})
        print(json.dumps(json.loads(result.content[0].text), indent=2))


if __name__ == "__main__":
    asyncio.run(main())
