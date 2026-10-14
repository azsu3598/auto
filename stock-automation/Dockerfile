FROM python:3.13-slim-trixie

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    TMPDIR=/tmp

# Refresh Debian security fixes even when the published base image lags behind.
RUN apt-get update \
    && apt-get upgrade -y --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY Kiwoom-REST-API /opt/kiwoom
COPY stock-automation/pyproject.toml /app/pyproject.toml
COPY stock-automation/src /app/src
RUN python -m pip install --no-cache-dir --upgrade pip \
    && python -m pip install --no-cache-dir --upgrade /opt/kiwoom . \
    && python -m pip check

# ECS copies this directory's ownership into the matching empty task volume.
# Keep all other image paths read-only at runtime.
RUN chown 65534:65534 /tmp && chmod 0700 /tmp
VOLUME ["/tmp"]

USER 65534:65534
ENTRYPOINT ["stock-automation"]
