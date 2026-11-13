from contextlib import AsyncExitStack
from mcp import ClientSession
from mcp.client.streamable_http import streamablehttp_client

class MCPProxy:
    def __init__(self, urls: dict[str, str]):
        self.urls = urls
        self._stack: AsyncExitStack | None = None
        self.sessions: dict[str, ClientSession] = {}

    async def start(self) -> None:
        self._stack = AsyncExitStack()
        for name, url in self.urls.items():
            read, write, _ = await self._stack.enter_async_context(streamablehttp_client(url))
            session = await self._stack.enter_async_context(ClientSession(read, write))
            await session.initialize()
            self.sessions[name] = session

    async def stop(self) -> None:
        if self._stack:
            await self._stack.aclose()
        self.sessions = {}

    async def call(self, server: str, tool: str, args: dict) -> str:
        result = await self.sessions[server].call_tool(tool, args)
        return "".join(c.text for c in result.content if hasattr(c, "text"))