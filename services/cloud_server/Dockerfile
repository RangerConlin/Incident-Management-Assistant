FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

WORKDIR /app

COPY services/cloud_server/requirements.txt /app/requirements.txt
COPY services/__init__.py /app/services/__init__.py
COPY services/cloud_server /app/services/cloud_server
COPY server/sarapp_db/sarapp_db /app/sarapp_db

# Not apt-installing docker.io here: that package drags in containerd, runc,
# and ~40 other packages (83MB+) this container never uses, since it only
# ever talks to the HOST's docker daemon over the bind-mounted socket below.
# The docker CLI + compose plugin are bind-mounted from the host instead
# (see docker-compose.yml) — the host's docker binary is effectively static
# (links only libc), so this is portable across the slim base image.
RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates git \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir -r /app/requirements.txt

EXPOSE 8000

CMD ["python", "-m", "services.cloud_server.main"]

