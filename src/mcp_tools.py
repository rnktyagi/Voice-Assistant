import asyncio
import os

from dotenv import load_dotenv
from langchain_mcp_adapters.client import MultiServerMCPClient

load_dotenv()

tavily_api_key = os.getenv("TAVILY_API_KEY")

client = MultiServerMCPClient(
    {
        "memory": {
            "transport": "streamable_http",
            "url": "https://mcp.mem0.ai/mcp",
            "headers": {
                "Authorization": f"Bearer {os.getenv('MEM0_API_KEY')}"
            },
        },
        "tavily": {
            "transport": "streamable_http", 
            "url": f"https://mcp.tavily.com/mcp/?tavilyApiKey={tavily_api_key}"
        }
    }
)

_mcp_tools_cache = None


async def get_mcp_tools():
    global _mcp_tools_cache

    if _mcp_tools_cache is not None:
        return _mcp_tools_cache

    try:
        tools = await client.get_tools()
        _mcp_tools_cache = tools

    except Exception as e:
        print("\n❌ Connection failed:")
        print(e)
        return []

    return _mcp_tools_cache