# Use the official Python 3.11 image
FROM python:3.11-slim

# Install uv (the package manager you are using)
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Set the working directory
WORKDIR /app

# Copy dependency files first to leverage Docker caching
COPY pyproject.toml uv.lock ./

# Sync dependencies (this creates a .venv in the container)
RUN uv sync --frozen --no-install-project

# Copy the rest of your code
COPY . .

# Install your project
RUN uv sync --frozen

# Expose the port (Render uses a PORT environment variable, we default to 8080)
ENV PORT=8080

# Start the Gateway
# We use shell form to allow the $PORT variable to be substituted by Render
CMD uv run uvicorn gateway.main:app --host 0.0.0.0 --port $PORT