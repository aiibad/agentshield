from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    # AuthN/AuthZ
    jwt_secret: str = "dev-secret-CHANGE-ME"
    jwt_algorithm: str = "HS256"
    jwt_exp_minutes: int = 120

    # Downstream MCP servers
    crm_url: str = "http://127.0.0.1:8001/mcp"
    email_url: str = "http://127.0.0.1:8002/mcp"

    # Gateway
    gateway_host: str = "127.0.0.1"
    gateway_port: int = 8080

    # Persistence
    audit_db: str = "gateway/audit.db"
    pin_store: str = "gateway/pins.json"

    model_config = SettingsConfigDict(env_prefix="AGENTSHIELD_", env_file=".env", extra="ignore")

settings = Settings()