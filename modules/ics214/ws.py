"""WebSocket endpoints for ICS-214 live updates."""
from __future__ import annotations

import asyncio
from collections import defaultdict
from typing import Dict, List, Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter()

class WebSocketManager:
    def __init__(self) -> None:
        self.connections: Dict[str, List[WebSocket]] = defaultdict(list)

    async def connect(self, stream_id: str, websocket: WebSocket) -> None:
        await websocket.accept()
        self.connections[stream_id].append(websocket)

    def disconnect(self, stream_id: str, websocket: WebSocket) -> None:
        if websocket in self.connections.get(stream_id, []):
            self.connections[stream_id].remove(websocket)

    def broadcast(self, stream_id: str, message: Dict[str, Any]) -> None:
        for ws in list(self.connections.get(stream_id, [])):
            try:
                loop = asyncio.get_running_loop()
                loop.create_task(ws.send_json(message))
            except RuntimeError:
                pass

manager = WebSocketManager()

@router.websocket("/streams/{stream_id}/ws")
async def stream_ws(websocket: WebSocket, stream_id: str):
    await manager.connect(stream_id, websocket)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(stream_id, websocket)
