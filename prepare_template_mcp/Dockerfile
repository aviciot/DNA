FROM python:3.12-slim

WORKDIR /app

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Copy requirements and install dependencies
COPY server/requirements.txt .
RUN uv pip install --system --no-cache -r requirements.txt

# Copy server code
COPY server/ .

# Expose port (configurable via environment)
EXPOSE 8000

# Run the server
CMD ["python", "server.py"]
