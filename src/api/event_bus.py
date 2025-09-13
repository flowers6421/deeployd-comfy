"""Simple event bus to broadcast build/execution events over WebSockets."""

from typing import Any

from src.api.websocket_manager import WebSocketManager

_manager: WebSocketManager | None = None


def set_manager(manager: WebSocketManager) -> None:
    global _manager
    _manager = manager


async def emit_build_event(
    build_id: str, message_type: str, data: dict[str, Any]
) -> None:
    if not _manager:
        return
    await _manager.broadcast_to_room(
        f"build:{build_id}", {"type": message_type, **data}
    )


async def emit_execution_event(
    execution_id: str, message_type: str, data: dict[str, Any]
) -> None:
    if not _manager:
        return
    await _manager.broadcast_to_room(
        f"execution:{execution_id}", {"type": message_type, **data}
    )
