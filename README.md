# AgentShield

Security gateway for AI agents: MCP security, prompt-injection defense,
guardrails, observability, and automated red-team evaluation.

> ⚠️ **Intentionally vulnerable.** `victim_app/` contains deliberately
> exploitable MCP servers (SQL injection, unlimited refunds, open email).
> For research and education only. Never deploy it on a public network.

## Status
Work in progress. v0.1: vulnerable baseline system + attack suite.

## Run locally
1. `uv sync`
2. `.\start_servers.ps1`
3. Set `LLM_BASE_URL`, `LLM_API_KEY`, `AGENT_MODEL` in your terminal (never commit keys)
4. `uv run python evals\baseline.py`