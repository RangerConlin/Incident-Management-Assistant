"""Universal incident export/import format.

Lets a whole incident (every incident-scoped collection plus its GridFS
attachments) be bundled into a single zip file on one server and restored
as a brand-new incident on another. See exporter.py / importer.py.
"""
