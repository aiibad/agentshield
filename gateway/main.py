import time
from contextlib import asynccontextmanager
from mcp.server.fastmcp import FastMCP
from .config import settings
from .policy import validate
from .proxy import MCPProxy
from .audit import log

ROUTES = {
    "search_customer": ("crm", "search_customer"),
    "get_ticket": ("crm", "get_ticket"),
    "issue_refund": ("crm", "issue_refund"),
    "send_email": ("email", "send_email"),
}

proxy = MCPProxy({"crm": settings.crm_url, "email": settings.email_url})

@asynccontextmanager
async def lifespan(mcp_app):
    print("Starting Gateway proxy...")
    try:
        await proxy.start()
        print("Gateway proxy started successfully!")
    except Exception as e:
        print(f"FAILED to start proxy: {e}")
    yield
    await proxy.stop()

mcp = FastMCP("agentshield-gateway", lifespan=lifespan, host=settings.gateway_host, port=settings.gateway_port)

async def _guarded(tool: str, args: dict) -> str:
    print(f"\n[GATEWAY] Received request for {tool} with args: {args}")
    t0 = time.perf_counter()
    agent = "test-agent"
    
    # 1. Run the policy check!
    ok, reason = validate(tool, args)
    if not ok:
        print(f"[GATEWAY] DENIED: {reason}")
        log(agent=agent, tool=tool, args=args, decision="deny", reason=reason, latency_ms=(time.perf_counter() - t0) * 1000)
        return f"DENIED: {reason}"

    # 2. If it passes, forward to the real server
    print(f"[GATEWAY] ALLOWED. Forwarding to {tool}...")
    server, remote_tool = ROUTES[tool]
    try:
        out = await proxy.call(server, remote_tool, args)
        log(agent=agent, tool=tool, args=args, decision="allow", reason="ok", latency_ms=(time.perf_counter() - t0) * 1000)
        return out
    except Exception as e:
        print(f"[GATEWAY] PROXY ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        return f"ERROR: {str(e)}"

@mcp.tool()
async def search_customer(name: str = "") -> str:
    """Search customers by name."""
    return await _guarded("search_customer", {"name": name})

@mcp.tool()
async def get_ticket(ticket_id: int) -> str:
    """Fetch a support ticket by id."""
    return await _guarded("get_ticket", {"ticket_id": ticket_id})

@mcp.tool()
async def issue_refund(customer_id: int, amount: float) -> str:
    """Issue a refund to a customer."""
    return await _guarded("issue_refund", {"customer_id": customer_id, "amount": amount})

@mcp.tool()
async def send_email(to: str, subject: str, body: str) -> str:
    """Send an email to any recipient."""
    return await _guarded("send_email", {"to": to, "subject": subject, "body": body})

if __name__ == "__main__":
    mcp.run(transport="streamable-http")