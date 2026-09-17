FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/apps/api \
    AEGISGRAPH_LOAD_ENV=false
WORKDIR /app

COPY requirements.lock pyproject.toml README.md LICENSE alembic.ini ./
COPY apps/api ./apps/api
COPY packages ./packages
COPY tests/fixtures ./tests/fixtures
RUN pip install --no-cache-dir -r requirements.lock \
    && useradd --create-home --uid 10001 aegisgraph

USER aegisgraph
CMD ["python", "-m", "aegisgraph.cli", "public-serve"]
