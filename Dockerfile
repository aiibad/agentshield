FROM python:3.11-slim

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Set the working directory
WORKDIR /app

# Copy dependency files first
COPY pyproject.toml uv.lock ./

# Sync dependencies
RUN uv sync --frozen --no-install-project

# Copy the rest of your code
COPY . .

# Install your project
RUN uv sync --frozen

# Expose the port
ENV PORT=8080

# Start the Gateway
# This command now correctly points to the 'app' variable in gateway/main.py
CMD uv run uvicorn gateway.main:app --host 0.0.0.0 --port $PORT