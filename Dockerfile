FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app

COPY pyproject.toml ./
RUN pip install --no-cache-dir -e ".[dev]" || pip install --no-cache-dir \
    fastapi "uvicorn[standard]" sqlalchemy alembic "psycopg[binary]" \
    pydantic pydantic-settings "python-jose[cryptography]" bcrypt \
    python-multipart jinja2 email-validator

COPY . .

EXPOSE 8000
CMD ["sh", "-c", "alembic upgrade head && python -m scripts.seed && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
