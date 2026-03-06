FROM python:3.12-slim

WORKDIR /app

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

COPY server/requirements.txt .
RUN uv pip install --system --no-cache -r requirements.txt

COPY server/ .

EXPOSE 8000

CMD ["python", "server.py"]
