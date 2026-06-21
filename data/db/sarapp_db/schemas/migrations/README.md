# sarapp_db/migrations — Schema Migration Scripts

Future migration scripts for evolving MongoDB document schemas live here.

## Conventions
- Number sequentially: `001_<description>.py`, `002_<description>.py`
- Each script must be idempotent (safe to re-run)
- Scripts should log what they changed and skip already-migrated documents
