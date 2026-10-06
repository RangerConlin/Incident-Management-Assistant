FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

WORKDIR /app

COPY cloud_server/requirements.txt /app/requirements.txt
COPY cloud_server /app/cloud_server
COPY data/db/sarapp_db /app/sarapp_db

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates git docker.io \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir -r /app/requirements.txt

EXPOSE 8000

CMD ["python", "-m", "cloud_server.main"]

