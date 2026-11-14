import time
import jwt
from fastapi import HTTPException
from .config import settings

# 1. Define what tools each scope is allowed to use
SCOPES = {
    "read":   ["search_customer", "get_ticket"],
    "refund": ["issue_refund"],
    "email":  ["send_email"],
}

def issue_token(agent_id: str, scopes: list[str]) -> str:
    """Generates a JWT token for an agent."""
    now = int(time.time())
    claims = {
        "sub": agent_id,
        "scopes": scopes,
        "iat": now,
        "exp": now + settings.jwt_exp_minutes * 60,
    }
    return jwt.encode(claims, settings.jwt_secret, algorithm=settings.jwt_algorithm)

def verify_token(token: str) -> dict:
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except jwt.PyJWTError:
        return None

def check_scope(claims: dict, tool: str) -> bool:
    """Checks if the token has permission to use this tool."""
    for scope, allowed_tools in SCOPES.items():
        if tool in allowed_tools:
            return scope in claims.get("scopes", [])
    return False