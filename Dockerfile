# Multi-stage Dockerfile for deploying Reflex 0.8.13 on Render (single container)
# Adapted to Python 3.12.3 (según tu entorno local) y evitando el bug de doble binding
# usando un backend interno en 127.0.0.1:8001 + Caddy como reverse proxy + static server.

# =============================
# 1) Builder stage
# =============================
FROM python:3.12.3-slim AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH"

WORKDIR /app

# Dependencias de compilación mínimas (algunas libs pueden necesitarlas futuramente)
RUN apt-get update -y && apt-get install -y --no-install-recommends \
    build-essential curl ca-certificates && \
    rm -rf /var/lib/apt/lists/*

# Crear y activar venv
RUN python -m venv /app/.venv

# Copiar requirements primero para aprovechar cache
COPY requirements.txt ./
RUN pip install --upgrade pip && pip install -r requirements.txt

# Copiamos config base antes de inicializar reflex (rxconfig.py requerido para init)
COPY rxconfig.py ./

# Inicializa estructura (.web). Si falla o ya existe, continuar.
RUN reflex init || true

# Copiar el resto del código (después para no invalidar caches antes de tiempo)
COPY . .

# Pre-build frontend (condicional). Reflex 0.8.13 puede NO tener comando export estable.
# Si existe el sub-comando `reflex export`, lo usamos para compilar assets; si no, lo omitimos.
# NOTA: No marcamos como error si falla, para permitir fallback runtime build.
RUN if reflex export --help >/dev/null 2>&1; then \
      echo "[builder] Ejecutando pre-build frontend (reflex export)..." && \
      REFLEX_API_URL=http://localhost:9999 reflex export --frontend-only --no-zip || echo "[builder] Advertencia: fallo export, se servirá dinámicamente"; \
    else \
      echo "[builder] 'reflex export' no disponible en esta versión; se omitirá pre-build"; \
    fi

# Si se generaron assets compilados, muévelos a /build-static (si no, la carpeta quedará vacía)
RUN mkdir -p /build-static && \
    if [ -d .web/build/client ]; then cp -R .web/build/client/* /build-static/ || true; fi

# =============================
# 2) Final stage
# =============================
FROM python:3.12.3-slim AS final

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH" \
    PORT=10000 \
    REFLEX_ENV=prod \
    REFLEX_DISABLE_RELOAD=1 \
    REFLEX_REDIS_URL=redis://localhost
# Nota: REFLEX_REDIS_URL es opcional; queda definido pero no afecta si la app no usa redis.

WORKDIR /app

# Instalar Caddy (proxy estático) y utilidades
RUN apt-get update -y && apt-get install -y --no-install-recommends caddy curl unzip && \
    rm -rf /var/lib/apt/lists/*

# Copiar venv y código desde builder
COPY --from=builder /app /app
# Copiar assets precompilados (si existen)
COPY --from=builder /build-static /srv

# Exponer puerto público (Render usará $PORT)
EXPOSE ${PORT}

# Caddyfile para servir estáticos y proxy a backend interno (127.0.0.1:8001)
# Se copia ahora para permitir override futuro via build arg si quieres.
COPY Caddyfile /etc/caddy/Caddyfile

# Script de entrada para:
# 1. Migrar DB.
# 2. Arrancar backend Reflex en 127.0.0.1:8001 (sin reload) en background.
# 3. Lanzar Caddy que sirve /srv (si existe) y hace proxy al backend.
# 4. Esperar proceso backend.
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

STOPSIGNAL SIGKILL

CMD ["/entrypoint.sh"]
