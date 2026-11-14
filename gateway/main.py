import time
from contextlib import asynccontextmanager
from mcp.server.fastmcp import FastMCP, Context
from .config import settings
from .policy import validate
from .proxy import MCPProxy
from .audit import log
from .auth import verify_token, check_scope

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
    await proxy.start()
    print("Gateway proxy started successfully!")
    yield
    await proxy.stop()

mcp = FastMCP("agentshield-gateway", lifespan=lifespan, host=settings.gateway_host, port=settings.gateway_port)

async def _guarded(tool: str, args: dict, ctx: Context) -> str:
    t0 = time.perf_counter()
    
    # 1. AUTHENTICATION: Check for JWT
    auth_header = ctx.request_context.request.headers.get("authorization", "")
    if not auth_header.startswith("Bearer "):
        return "DENIED: Missing bearer token"
        
    token = auth_header[7:]
    claims = verify_token(token)
    if not claims:
        return "DENIED: Invalid or expired token"
        
    agent = claims.get("sub", "unknown")

    # 2. AUTHORIZATION: Check Scopes
    if not check_scope(claims, tool):
        reason = f"Agent '{agent}' lacks scope for '{tool}'"
        log(agent=agent, tool=tool, args=args, decision="deny", reason=reason, latency_ms=0)
        return f"DENIED: {reason}"

    print(f"\n[GATEWAY] Auth OK for {agent}. Received {tool} with args: {args}")

    # 3. POLICY: Check arguments (email allowlist, refund limit, SQLi)
    ok, reason = validate(tool, args)
    if not ok:
        print(f"[GATEWAY] POLICY DENIED: {reason}")
        log(agent=agent, tool=tool, args=args, decision="deny", reason=reason, latency_ms=(time.perf_counter() - t0) * 1000)
        return f"DENIED: {reason}"

    # 4. FORWARD TO REAL SERVER
    print(f"[GATEWAY] ALLOWED. Forwarding to {tool}...")
    server, remote_tool = ROUTES[tool]
    try:
        out = await proxy.call(server, remote_tool, args)
        log(agent=agent, tool=tool, args=args, decision="allow", reason="ok", latency_ms=(time.perf_counter() - t0) * 1000)
        return out
    except Exception as e:
        print(f"[GATEWAY] PROXY ERROR: {str(e)}")
        return f"ERROR: {str(e)}"

# Notice we added `ctx: Context` to all tools so the Gateway can read the headers
@mcp.tool()
async def search_customer(name: str = "", ctx: Context = None) -> str:
    """Search customers by name."""
    return await _guarded("search_customer", {"name": name}, ctx)

@mcp.tool()
async def get_ticket(ticket_id: int, ctx: Context = None) -> str:
    """Fetch a support ticket by id."""
    return await _guarded("get_ticket", {"ticket_id": ticket_id}, ctx)

@mcp.tool()
async def issue_refund(customer_id: int, amount: float, ctx: Context = None) -> str:
    """Issue a refund to a customer."""
    return await _guarded("issue_refund", {"customer_id": customer_id, "amount": amount}, ctx)

@mcp.tool()
async def send_email(to: str, subject: str, body: str, ctx: Context = None) -> str:
    """Send an email to any recipient."""
    return await _guarded("send_email", {"to": to, "subject": subject, "body": body}, ctx)

if __name__ == "__main__":
    mcp.run(transport="streamable-http")