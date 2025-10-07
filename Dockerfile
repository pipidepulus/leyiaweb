## Route A: Simplified single-stage Dockerfile for Reflex on Render
## - Sin Caddy, sin Redis, sin proxy interno.
## - Usa Python 3.12.3 (alineado con tu entorno local).
## - Ejecuta migraciones y luego levanta el backend en $PORT.
## - Intento opcional de pre-build del frontend (no crítico si falla).

ARG PORT=10000

FROM python:3.12.3-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
        PYTHONUNBUFFERED=1 \
        REFLEX_ENV=prod \
        PORT=${PORT}

WORKDIR /app

# Dependencias básicas de compilación (ampliar sólo si alguna lib lo requiere)
RUN apt-get update -y && apt-get install -y --no-install-recommends build-essential curl ca-certificates && \
        rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install --upgrade pip && pip install -r requirements.txt

COPY rxconfig.py ./
RUN reflex init || true

COPY . .

# Precompilar (si la versión soporta 'reflex export'). No es obligatorio para correr.
RUN if reflex export --help >/dev/null 2>&1; then \
            echo "[build] Ejecutando pre-build de frontend" && \
            REFLEX_API_URL=http://localhost:${PORT} reflex export --frontend-only --no-zip || echo "[build] Advertencia: export falló; se generará en runtime"; \
        else \
            echo "[build] 'reflex export' no disponible en esta versión"; \
        fi

EXPOSE ${PORT}

# CMD: migrar (idempotente) y arrancar backend único.
CMD reflex db migrate && exec reflex run --env prod --backend-only --backend-host 0.0.0.0 --backend-port ${PORT}