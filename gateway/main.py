import os
import time
from contextlib import asynccontextmanager
from mcp.server.fastmcp import FastMCP, Context
from fastapi import FastAPI
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
IS_RENDER = bool(os.environ.get("RENDER"))

@asynccontextmanager
async def lifespan(app: FastAPI):
    if not IS_RENDER:
        print("Starting Gateway proxy...")
        try:
            await proxy.start()
            print("Gateway proxy started successfully!")
        except BaseException as e:
            print(f"WARNING: Could not connect to local MCP servers: {e}")
    else:
        print("Running on Render: Skipping proxy start (local MCP servers not available).")
    yield
    if not IS_RENDER:
        try:
            await proxy.stop()
        except:
            pass

mcp = FastMCP("agentshield-gateway")

async def _guarded(tool: str, args: dict, ctx: Context) -> str:
    t0 = time.perf_counter()
    
    auth_header = ctx.request_context.request.headers.get("authorization", "")
    if not auth_header.startswith("Bearer "):
        return "DENIED: Missing bearer token"
        
    token = auth_header[7:]
    claims = verify_token(token)
    if not claims:
        return "DENIED: Invalid or expired token"
        
    agent = claims.get("sub", "unknown")

    if not check_scope(claims, tool):
        reason = f"Agent '{agent}' lacks scope for '{tool}'"
        log(agent=agent, tool=tool, args=args, decision="deny", reason=reason, latency_ms=0)
        return f"DENIED: {reason}"

    ok, reason = validate(tool, args)
    if not ok:
        log(agent=agent, tool=tool, args=args, decision="deny", reason=reason, latency_ms=(time.perf_counter() - t0) * 1000)
        return f"DENIED: {reason}"

    server, remote_tool = ROUTES[tool]
    try:
        out = await proxy.call(server, remote_tool, args)
        log(agent=agent, tool=tool, args=args, decision="allow", reason="ok", latency_ms=(time.perf_counter() - t0) * 1000)
        return out
    except Exception as e:
        return f"ERROR: {str(e)}"

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

app = FastAPI(title="AgentShield Gateway", lifespan=lifespan)
mcp_app = mcp.streamable_http_app()
app.mount("/mcp", mcp_app)
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
    
    # Mock results for the live demo (since MCP servers are local)
    mock_results = {
        "send_email": f"Email sent to {req.args.get('to')}",
        "issue_refund": f"Refunded {req.args.get('amount')} to customer {req.args.get('customer_id')}",
        "search_customer": "[{'id': 1, 'name': 'Asha Patil', 'email': 'asha@example.com'}]",
        "get_ticket": "Ticket #1: My order #123 has not arrived."
    }
    return {"status": "allowed", "result": mock_results.get(real_tool, "Success")}