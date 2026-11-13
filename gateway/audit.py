import json
import time
from pathlib import Path

def log(*, agent: str, tool: str, args: dict, decision: str, reason: str, latency_ms: float) -> None:
    try:
        log_file = Path("gateway/audit.log")
        log_file.parent.mkdir(parents=True, exist_ok=True)
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps({
                "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
                "agent": agent,
                "tool": tool,
                "args": args,
                "decision": decision,
                "reason": reason,
                "latency_ms": round(latency_ms, 2)
            }) + "\n")
    except Exception as e:
        print(f"Audit log failed: {e}")