#!/bin/bash
set -e

echo "=== STTA-DVF Production Start ==="
echo "PORT: ${PORT:-8000}"

# Default port
export PORT=${PORT:-8000}

# Generate nginx config from template
envsubst '${PORT}' < /app/deploy/nginx.conf.template > /etc/nginx/conf.d/default.conf

# Remove default nginx site
rm -f /etc/nginx/sites-enabled/default

# Start FastAPI (background)
echo "Starting FastAPI on :8001..."
uvicorn src.api.main:app \
    --host 127.0.0.1 \
    --port 8001 \
    --workers 2 \
    --timeout-keep-alive 65 \
    --log-level info &

# Start Streamlit (background)
echo "Starting Streamlit on :8501..."
streamlit run src/app/streamlit_app.py \
    --server.port 8501 \
    --server.address 127.0.0.1 \
    --server.headless true \
    --server.enableCORS false \
    --server.enableXsrfProtection false \
    --browser.gatherUsageStats false &

# Wait for backends to be ready
sleep 3

# Start nginx (foreground — keeps container alive)
echo "Starting nginx on :${PORT}..."
nginx -g "daemon off;"
