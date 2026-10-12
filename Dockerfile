FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PYTHONPATH=/app
ENV RUFF_CACHE_DIR=/tmp/ruff-cache
WORKDIR /app
COPY requirements.lock ./
RUN pip install --no-cache-dir -r requirements.lock
COPY pyproject.toml alembic.ini ./
COPY ledgerlite ./ledgerlite
COPY migrations ./migrations
COPY tests ./tests
COPY scripts ./scripts
RUN pip install --no-deps . && useradd --create-home appuser
USER appuser
CMD ["uvicorn", "ledgerlite.wallet.app:app", "--host", "0.0.0.0", "--port", "8000"]
