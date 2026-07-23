# syntax=docker/dockerfile:1.7
#
# Imagen para Cloud Run Job `factory-etl`.
# Multi-stage: builder aisla toolchain, runtime queda minimo y sin root.

# --- Stage 1: builder --------------------------------------------------------

FROM python:3.12-slim-bookworm AS builder

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    UV_LINK_MODE=copy

WORKDIR /build

# Instalar uv (usa la imagen oficial via COPY --from para no ejecutar scripts remotos)
COPY --from=ghcr.io/astral-sh/uv:0.4.20 /uv /usr/local/bin/uv

# Copiar unicamente los archivos que definen el entorno para maximizar cache
COPY pyproject.toml uv.lock* README.md ./
COPY src ./src

# Crear venv reproducible sin dev deps
RUN uv sync --frozen --no-dev --no-editable

# --- Stage 2: runtime --------------------------------------------------------

FROM python:3.12-slim-bookworm AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/app/.venv/bin:$PATH" \
    FACTORY_ETL_ENV=prod

# Usuario no privilegiado
RUN groupadd --system --gid 10001 app \
 && useradd --system --uid 10001 --gid app --home-dir /app --shell /sbin/nologin app

WORKDIR /app

# Traer venv y codigo desde builder
COPY --from=builder --chown=app:app /build/.venv /app/.venv
COPY --from=builder --chown=app:app /build/src /app/src

# Endurecimiento: eliminar herramientas de shell interactivo, evitar cache
RUN find / -xdev -perm -4000 -type f -exec chmod a-s {} \; 2>/dev/null || true

USER 10001:10001

ENTRYPOINT ["python", "-m", "factory_etl"]
CMD []
