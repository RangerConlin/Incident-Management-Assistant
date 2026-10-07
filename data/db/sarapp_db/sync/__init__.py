"""Central-master sync relay: pushes local master-catalog writes to
cloud_router's embedded central database, and pulls down changes made
there (by another server, or through the central web GUI).

See Design Documents/Instructions/cloud_router_architecture.md and
Design Documents/Instructions/realtime_architecture_roadmap.md for the
surrounding architecture and why this is push-on-write-with-an-outbox
rather than MongoDB change streams (change streams need a replica set;
nothing in this product runs one today).
"""
