## Simplified single-stage Dockerfile for Reflex on Render (Python 3.12.3)
## Basado en el ejemplo oficial, sólo adaptando la versión de Python y usando PORT=10000.

ARG PORT=10000
ARG API_URL

FROM python:3.12.3-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    REFLEX_ENV=prod \
    PORT=${PORT}

WORKDIR /app

# Dependencias mínimas de compilación (puedes ampliar si tus libs lo requieren)
RUN apt-get update -y && apt-get install -y --no-install-recommends build-essential curl ca-certificates && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install --upgrade pip && pip install -r requirements.txt

# Copiar configuración antes de init
COPY rxconfig.py ./
RUN reflex init || true

# Copiar el resto del proyecto
COPY . .

# Precompilar frontend si el comando export está disponible (no es crítico si falla)
RUN if reflex export --help >/dev/null 2>&1; then \
      echo "[build] Precompilando frontend" && \
      REFLEX_API_URL=${API_URL:-http://localhost:${PORT}} reflex export --frontend-only --no-zip || echo "[build] Advertencia: export falló, se generará en runtime"; \
    else \
      echo "[build] 'reflex export' no disponible en esta versión"; \
    fi

EXPOSE ${PORT}

# Aplicar migraciones antes de arrancar. 'reflex db migrate' cubre init/update.
CMD reflex db migrate && exec reflex run --env prod --backend-only --backend-host 0.0.0.0 --backend-port ${PORT}
