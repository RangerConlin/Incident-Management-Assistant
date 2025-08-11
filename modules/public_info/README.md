# Public Information Module

This module provides Public Information Officer (PIO) capabilities for the ICS Command Assistant desktop application.

## Purpose
Handles drafting, approval, publishing, and archiving of public information messages for a mission.

## Running locally
1. Ensure dependencies are installed: `pip install -r requirements.txt`.
2. Initialize the mission database and seed sample data:
   ```bash
   python -m modules.public_info.seed
   ```
3. Run the FastAPI app or main application and navigate to the PIO screens.

## API Endpoints
Mounted under `/api/public_info`:
- `GET /messages`
- `POST /messages`
- `GET /messages/{id}`
- `PUT /messages/{id}`
- `POST /messages/{id}/submit`
- `POST /messages/{id}/approve`
- `POST /messages/{id}/publish`
- `POST /messages/{id}/archive`
- `GET /history`
- `GET /export/{id}.pdf`

## UI
Open the PIO screens from the main app menu by creating instances of the panels in `modules/public_info/panels` or loading the QML files in `modules/public_info/qml`.
