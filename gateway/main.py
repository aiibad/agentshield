import time
from contextlib import asynccontextmanager
from mcp.server.fastmcp import FastMCP, Context
from fastapi import Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

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
    try:
        await proxy.start()
        print("Gateway proxy started successfully!")
    except Exception as e:
        print(f"WARNING: Could not connect to local MCP servers: {e}")
        print("Gateway is running in standalone mode (policies/auth will still work).")
    yield
    try:
        await proxy.stop()
    except:
        pass

# 1. Initialize MCP FIRST
mcp = FastMCP("agentshield-gateway", lifespan=lifespan, host=settings.gateway_host, port=settings.gateway_port)

async def _guarded(tool: str, args: dict, ctx: Context) -> str:
    t0 = time.perf_counter()
    
    # AUTHENTICATION
    auth_header = ctx.request_context.request.headers.get("authorization", "")
    if not auth_header.startswith("Bearer "):
        return "DENIED: Missing bearer token"
        
    token = auth_header[7:]
    claims = verify_token(token)
    if not claims:
        return "DENIED: Invalid or expired token"
        
    agent = claims.get("sub", "unknown")

    # AUTHORIZATION (Scopes)
    if not check_scope(claims, tool):
        reason = f"Agent '{agent}' lacks scope for '{tool}'"
        log(agent=agent, tool=tool, args=args, decision="deny", reason=reason, latency_ms=0)
        return f"DENIED: {reason}"

    # POLICY (Arguments)
    ok, reason = validate(tool, args)
    if not ok:
        log(agent=agent, tool=tool, args=args, decision="deny", reason=reason, latency_ms=(time.perf_counter() - t0) * 1000)
        return f"DENIED: {reason}"

    # FORWARD
    server, remote_tool = ROUTES[tool]
    try:
        out = await proxy.call(server, remote_tool, args)
        log(agent=agent, tool=tool, args=args, decision="allow", reason="ok", latency_ms=(time.perf_counter() - t0) * 1000)
        return out
    except Exception as e:
        return f"ERROR: {str(e)}"

# 2. Define MCP Tools SECOND
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

# 3. Create the FastAPI App THIRD
app = mcp.streamable_http_app()

# 4. Add UI Routes LAST
app.mount("/static", StaticFiles(directory="gateway/static"), name="static")

@app.get("/", response_class=HTMLResponse)
async def serve_ui():
    with open("gateway/static/index.html", "r", encoding="utf-8") as f:
        return f.read()

class AttackRequest(BaseModel):
    tool: str
    args: dict

@app.post("/api/test-attack")
async def test_attack(req: AttackRequest):
    tool_map = {
        "email": "send_email",
        "refund": "issue_refund",
        "search": "search_customer",
        "ticket": "get_ticket"
    }
    real_tool = tool_map.get(req.tool)
    
    ok, reason = validate(real_tool, req.args)
    if not ok:
        log(agent="web-ui", tool=real_tool, args=req.args, decision="deny", reason=reason, latency_ms=0)
        return {"status": "denied", "reason": reason}
    
    return {"status": "allowed", "result": "Passed security policies! (Local servers are offline in this demo)"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=settings.gateway_host, port=settings.gateway_port)