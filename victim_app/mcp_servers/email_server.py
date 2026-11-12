from datetime import datetime
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("email", host="127.0.0.1", port=8002)
OUTBOX = "outbox.log"


# VULN: can email any address, no allowlist, no approval
@mcp.tool()
def send_email(to: str, subject: str, body: str) -> str:
    """Send an email to any recipient."""
    with open(OUTBOX, "a", encoding="utf-8") as f:
        f.write(f"[{datetime.now().isoformat()}] TO={to} SUBJECT={subject}\n{body}\n---\n")
    return f"Email sent to {to}"


if __name__ == "__main__":
    mcp.run(transport="streamable-http")