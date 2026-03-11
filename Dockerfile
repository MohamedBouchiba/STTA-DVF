FROM python:3.12-slim

WORKDIR /app

# Dependances systeme pour psycopg2
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev gcc \
    && rm -rf /var/lib/apt/lists/*

# Dependances Python
COPY requirements-api.txt .
RUN pip install --no-cache-dir -r requirements-api.txt

# Code source
COPY src/ src/

# Railway injecte $PORT (defaut 8000 en local)
ENV PORT=8000

EXPOSE ${PORT}

CMD uvicorn src.api.main:app --host 0.0.0.0 --port ${PORT} --workers 2 --timeout-keep-alive 65
