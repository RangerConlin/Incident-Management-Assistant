"""Universal incident and master-catalog export/import formats.

`exporter.py` / `importer.py` bundle a whole incident (every incident-scoped
collection plus its GridFS attachments) into a single zip file on one server
and restore it as a brand-new incident on another.

`master_exporter.py` bundles every master-catalog collection into a similar
zip, for backing up or transferring a server's reference-data catalogs.
"""
