FROM python:3.12-slim

WORKDIR /app

# Build context is the repo root (see docker-compose.yml) so this image can
# also vendor the shared sarapp_db package for the embedded central master
# database — same layout cloud_server/Dockerfile uses.
COPY cloud_router/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY cloud_router /app
COPY data/db/sarapp_db /app/sarapp_db

ENV PYTHONPATH=/app

EXPOSE 8765

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8765/health', timeout=3).status == 200 else 1)"

CMD ["python", "main.py", "--host", "0.0.0.0", "--port", "8765"]
