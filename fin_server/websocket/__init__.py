"""WebSocket module for real-time communication.

This module provides:
- Centralized WebSocket Hub
- Event Emitter for notifications, alerts, chat, and streams
- Handlers for different event types
"""

from fin_server.websocket.event_emitter import EventEmitter
from fin_server.websocket.hub import WebSocketHub

__all__ = ['EventEmitter', 'WebSocketHub']

