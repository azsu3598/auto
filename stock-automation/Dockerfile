FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app
COPY Kiwoom-REST-API /opt/kiwoom
COPY stock-automation/pyproject.toml /app/pyproject.toml
COPY stock-automation/src /app/src
RUN pip install --no-cache-dir /opt/kiwoom .

USER 65534:65534
ENTRYPOINT ["stock-automation"]
