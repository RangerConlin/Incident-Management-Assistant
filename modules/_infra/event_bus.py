"""Simple in-process asyncio pub/sub event bus."""

import asyncio
from collections import defaultdict
from typing import Any, Dict, List

class EventBus:
    def __init__(self) -> None:
        self._subscribers: Dict[str, List[asyncio.Queue]] = defaultdict(list)

    async def publish(self, topic: str, message: Dict[str, Any]) -> None:
        queues = list(self._subscribers.get(topic, []))
        for queue in queues:
            await queue.put(message)

    def subscribe(self, topic: str) -> "asyncio.Queue":
        queue: asyncio.Queue = asyncio.Queue()
        self._subscribers[topic].append(queue)
        return queue

    def unsubscribe(self, topic: str, queue: "asyncio.Queue") -> None:
        if queue in self._subscribers.get(topic, []):
            self._subscribers[topic].remove(queue)

# Global singleton bus
bus = EventBus()
