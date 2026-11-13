import re

# 1. Block SQL injection attempts
_SQLI = re.compile(r"('\s*or\s*'|--|;|union\s+select)", re.I)

# 2. Only allow emails to internal/approved domains
_SAFE_EMAIL = re.compile(r"^[a-z0-9._%+-]+@(company\.com|example\.com)$", re.I)

# 3. Hard limit for refunds
REFUND_LIMIT = 500.0

def validate(tool: str, args: dict) -> tuple[bool, str]:
    if tool == "search_customer":
        name = str(args.get("name", ""))
        if _SQLI.search(name):
            return False, "possible SQL injection in 'name'"

    if tool == "issue_refund":
        try:
            amt = float(args.get("amount", 0))
        except (TypeError, ValueError):
            return False, "amount must be numeric"
        if amt <= 0:
            return False, "amount must be positive"
        if amt > REFUND_LIMIT:
            return False, f"refund {amt} exceeds limit {REFUND_LIMIT}"

    if tool == "send_email":
        to = str(args.get("to", ""))
        if not _SAFE_EMAIL.match(to):
            return False, f"recipient '{to}' not on allowlist"

    return True, "ok"