"""Logistics module router — superseded by sarapp_db FastAPI routers.

Resource requests and resource status are handled by:
  data/db/sarapp_db/api/routers/logistics_resource_requests.py
  data/db/sarapp_db/api/routers/logistics_resource_status.py
"""
from fastapi import APIRouter

router = APIRouter(tags=["logistics"])
