#!/usr/bin/env bash
set -euo pipefail

# Variables
BACKEND_HOST=127.0.0.1
BACKEND_PORT=8001
PUBLIC_PORT=${PORT:-10000}

echo "[entrypoint] Reflex env: $REFLEX_ENV  Public port (Caddy): $PUBLIC_PORT  Internal backend: $BACKEND_HOST:$BACKEND_PORT"

# Asegurar dependencias construidas (en caso de fallback)
if [ ! -d .web ]; then
  echo "[entrypoint] .web no existe; ejecutando 'reflex init'" && reflex init || true
fi

# Migraciones (no falla si ya está al día)
if [ -d alembic ]; then
  echo "[entrypoint] Aplicando migraciones..."
  reflex db migrate || echo "[entrypoint] Advertencia: migrate retornó código no cero (posible sin cambios)"
fi

# Lanzar backend en background
(
  echo "[entrypoint] Iniciando backend Reflex (sin reload) en ${BACKEND_HOST}:${BACKEND_PORT}";
  REFLEX_DISABLE_RELOAD=1 reflex run --env prod --backend-only --backend-host ${BACKEND_HOST} --backend-port ${BACKEND_PORT}
) &
BACK_PID=$!

# Dar unos segundos para que arranque
sleep 2

# Iniciar Caddy (sirve estáticos en /srv y proxy al backend interno)
echo "[entrypoint] Iniciando Caddy en :${PUBLIC_PORT}";
exec caddy run --config /etc/caddy/Caddyfile --adapter caddyfile
