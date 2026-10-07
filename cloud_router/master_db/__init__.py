"""Embedded central master-catalog database for cloud_router.

See Design Documents/Instructions/cloud_router_architecture.md for the full
architecture. This package wires cloud_router's own MongoDB instance to the
existing agency-wide master-catalog routers in ``sarapp_db`` (personnel,
equipment, vehicles, aircraft, hospitals, certifications, organizations,
templates, forms, etc.) without duplicating any of that router/schema code.
"""
