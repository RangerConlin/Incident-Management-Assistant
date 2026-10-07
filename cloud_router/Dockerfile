FROM python:3.12-slim

WORKDIR /app

# Build context is the repo root (see docker-compose.yml) so this image can
# also vendor the shared sarapp_db package for the embedded central master
# database — same layout cloud_server/Dockerfile uses.
COPY cloud_router/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY cloud_router /app
COPY data/db/sarapp_db /app/sarapp_db

# The web GUI's personnel import/export shares its field list and row
# mapping with the desktop Edit-menu panel (modules/personnel/catalog_io.py,
# modules/logistics/equipment_catalog_io.py — see cloud_router/master_db/
# webgui.py) rather than duplicating it, so this image needs those specific
# modules/ files even though the rest of modules/ (which depends on Qt) is
# not included here. cert_catalog.py is catalog_io.py's own dependency
# (the hardcoded certification catalog it reads).
COPY modules/__init__.py /app/modules/__init__.py
COPY modules/personnel/__init__.py /app/modules/personnel/__init__.py
COPY modules/personnel/catalog_io.py /app/modules/personnel/catalog_io.py
COPY modules/personnel/models/cert_catalog.py /app/modules/personnel/models/cert_catalog.py
COPY modules/logistics/__init__.py /app/modules/logistics/__init__.py
COPY modules/logistics/equipment_catalog_io.py /app/modules/logistics/equipment_catalog_io.py

ENV PYTHONPATH=/app

EXPOSE 8765

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8765/health', timeout=3).status == 200 else 1)"

CMD ["python", "main.py", "--host", "0.0.0.0", "--port", "8765"]
