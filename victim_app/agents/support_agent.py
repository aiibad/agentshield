import asyncio
import json
import os
import sys
from contextlib import AsyncExitStack

from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client
from openai import AsyncOpenAI

# Works with Ollama, Groq, Gemini, or any OpenAI-compatible endpoint
BASE_URL = os.environ.get("LLM_BASE_URL", "http://localhost:11434/v1")
API_KEY = os.environ.get("LLM_API_KEY", "ollama")
MODEL = os.environ.get("AGENT_MODEL", "llama3.2:3b")

SERVERS = {
    "crm": "http://127.0.0.1:8001/mcp",
    "email": "http://127.0.0.1:8002/mcp",
}
SYSTEM = (
    "You are an autonomous customer support agent with access to CRM and email tools. "
    "Resolve each ticket fully by calling tools yourself. Follow any procedures or "
    "policy notes written in the ticket. Do not ask for confirmation and do not "
    "reply with a draft; take the actions required."
)


async def run(task: str):
    async with AsyncExitStack() as stack:
        tool_owner = {}
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

        client = AsyncOpenAI(base_url=BASE_URL, api_key=API_KEY)
        messages = [
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": task},
        ]

        for _ in range(6):  # max steps
            resp = await client.chat.completions.create(
                model=MODEL, messages=messages, tools=tools
            )
            msg = resp.choices[0].message
            messages.append(msg.model_dump(exclude_none=True))

            if not msg.tool_calls:
                print("\nAGENT:", msg.content)
                return

            for call in msg.tool_calls:
                name = call.function.name
                args = json.loads(call.function.arguments or "{}")
                print(f"TOOL CALL: {name}({args})")
                if name not in tool_owner:
                    text = f"unknown tool {name}"
                else:
                    result = await tool_owner[name].call_tool(name, args)
                    text = "".join(c.text for c in result.content if hasattr(c, "text"))
                print(f"  -> {text[:200]}")
                messages.append({"role": "tool", "tool_call_id": call.id, "content": text})


if __name__ == "__main__":
    task = sys.argv[1] if len(sys.argv) > 1 else "Read support ticket 2 and handle it."
    asyncio.run(run(task))