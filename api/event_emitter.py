"""
Event Emitter for SSE streaming.
Wraps an asyncio.Queue to emit structured events from LangGraph nodes.
"""

import asyncio
import json
from datetime import datetime, timezone
from typing import Any, Dict, Optional


class EventEmitter:
    """Emits structured SSE events from agent nodes to the streaming endpoint."""

    def __init__(self):
        self.queue: asyncio.Queue = asyncio.Queue()
        self.logs: list = []
        self.agent_trace: list = []

    def _timestamp(self) -> str:
        return datetime.now(timezone.utc).isoformat()

    def _put(self, event: Dict[str, Any]):
        """Synchronous put — safe to call from sync LangGraph nodes."""
        try:
            self.queue.put_nowait(event)
        except asyncio.QueueFull:
            pass  # Drop event if queue is full (shouldn't happen)

    def emit_log(self, step: str, message: str, data: Optional[Dict] = None):
        """Emit an informational log message."""
        event = {
            "type": "log",
            "step": step,
            "status": "running",
            "message": message,
            "data": data or {},
            "timestamp": self._timestamp(),
        }
        self.logs.append(event)
        self._put(event)

    def emit_step(self, step: str, status: str, message: str = "", data: Optional[Dict] = None):
        """Emit a step status update (running / completed / failed)."""
        event = {
            "type": "step",
            "step": step,
            "status": status,
            "message": message,
            "data": data or {},
            "timestamp": self._timestamp(),
        }
        self.agent_trace.append({"step": step, "status": status, "timestamp": event["timestamp"]})
        self._put(event)

    def emit_result(self, data: Dict[str, Any]):
        """Emit the final aggregated result."""
        event = {
            "type": "result",
            "step": "final",
            "status": "completed",
            "message": "Processing complete",
            "data": data,
            "timestamp": self._timestamp(),
        }
        self._put(event)

    def emit_error(self, step: str, message: str, data: Optional[Dict] = None):
        """Emit an error event."""
        event = {
            "type": "error",
            "step": step,
            "status": "failed",
            "message": message,
            "data": data or {},
            "timestamp": self._timestamp(),
        }
        self.logs.append(event)
        self._put(event)

    async def stream(self):
        """Async generator that yields events from the queue as SSE data strings."""
        while True:
            try:
                event = await asyncio.wait_for(self.queue.get(), timeout=300)
                yield json.dumps(event)
                # Stop streaming after final result or error
                if event["type"] in ("result",):
                    break
            except asyncio.TimeoutError:
                # Send keepalive
                yield json.dumps({"type": "log", "step": "system", "status": "running",
                                  "message": "Still processing...", "data": {}, "timestamp": self._timestamp()})
            except Exception:
                break

    def emit_done(self):
        """Signal that streaming is complete."""
        self._put({"type": "done", "step": "system", "status": "completed",
                    "message": "Stream ended", "data": {}, "timestamp": self._timestamp()})
