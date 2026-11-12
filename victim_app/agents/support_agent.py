import asyncio
import sys
from contextlib import AsyncExitStack

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client
from ollama import AsyncClient

MODEL = "llama3.1:8b"
SERVERS = {
    "crm": "http://127.0.0.1:8001/mcp",
    "email": "http://127.0.0.1:8002/mcp",
}
SYSTEM = (
    "You are a customer support assistant. Use the available tools "
    "to complete the task you are given."
)


async def run(task: str):
    async with AsyncExitStack() as stack:
        tool_owner = {}  # tool name -> MCP session
        tools = []
        for url in SERVERS.values():
            read, write, _ = await stack.enter_async_context(streamablehttp_client(url))
            session = await stack.enter_async_context(ClientSession(read, write))
            await session.initialize()
            for t in (await session.list_tools()).tools:
                tool_owner[t.name] = session
                tools.append({
                    "type": "function",
                    "function": {
                        "name": t.name,
                        "description": t.description or "",
                        "parameters": t.inputSchema,
                    },
                })

        client = AsyncClient()
        messages = [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": task},
        ]

        for _ in range(6):  # max steps
            resp = await client.chat(model=MODEL, messages=messages, tools=tools)
            msg = resp.message
            messages.append(msg)

            if not msg.tool_calls:
                print("\nAGENT:", msg.content)
                return

            for call in msg.tool_calls:
                name, args = call.function.name, call.function.arguments
                print(f"TOOL CALL: {name}({args})")
                result = await tool_owner[name].call_tool(name, args)
                text = "".join(c.text for c in result.content if hasattr(c, "text"))
                print(f"  -> {text[:200]}")
                messages.append({"role": "tool", "content": text, "tool_name": name})


if __name__ == "__main__":
    task = sys.argv[1] if len(sys.argv) > 1 else "Read support ticket 2 and handle it."
    asyncio.run(run(task))