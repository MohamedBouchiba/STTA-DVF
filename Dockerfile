FROM python:3.12-slim

WORKDIR /app

# Dependances systeme: PostgreSQL client, nginx, envsubst
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq-dev gcc nginx gettext-base \
    && rm -rf /var/lib/apt/lists/*

# Dependances Python
COPY requirements-api.txt .
RUN pip install --no-cache-dir -r requirements-api.txt

# Code source
COPY src/ src/

# Scripts de deploiement (nginx conf + entrypoint)
COPY deploy/ deploy/
RUN chmod +x deploy/start.sh

# Railway injecte $PORT (defaut 8000 en local)
ENV PORT=8000

EXPOSE ${PORT}

CMD ["bash", "deploy/start.sh"]
