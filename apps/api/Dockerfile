FROM python:3.12-slim
WORKDIR /app
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv
COPY pyproject.toml uv.lock* ./
COPY apps/api apps/api
COPY packages/ingest packages/ingest
RUN uv sync --package mizaj --no-dev
ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONPATH=/app/apps/api/src
EXPOSE 8000
CMD ["uvicorn", "mizaj.main:app", "--host", "127.0.0.1", "--port", "8000"]
