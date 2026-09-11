import asyncio
import json
from typing import Dict, Set
from fastapi import WebSocket, WebSocketDisconnect


class ConnectionManager:
    """Manage WebSocket connections for real-time updates"""
    
    def __init__(self):
        # session_id -> set of WebSocket connections
        self.active_connections: Dict[str, Set[WebSocket]] = {}
    
    async def connect(self, websocket: WebSocket, session_id: str):
        """Accept and register a new WebSocket connection"""
        await websocket.accept()
        
        if session_id not in self.active_connections:
            self.active_connections[session_id] = set()
        
        self.active_connections[session_id].add(websocket)
        print(f"[WebSocket] Client connected to session {session_id}")
    
    def disconnect(self, websocket: WebSocket, session_id: str):
        """Remove a WebSocket connection"""
        if session_id in self.active_connections:
            self.active_connections[session_id].discard(websocket)
            
            # Clean up empty session
            if not self.active_connections[session_id]:
                del self.active_connections[session_id]
        
        print(f"[WebSocket] Client disconnected from session {session_id}")
    
    async def send_event(self, session_id: str, event: dict):
        """Send event to all connected clients for a session"""
        if session_id not in self.active_connections:
            return
        
        message = json.dumps(event)
        dead_connections = set()
        
        for connection in self.active_connections[session_id]:
            try:
                await connection.send_text(message)
            except Exception as e:
                print(f"[WebSocket] Failed to send to client: {e}")
                dead_connections.add(connection)
        
        # Clean up dead connections
        for connection in dead_connections:
            self.disconnect(connection, session_id)
    
    async def broadcast_status_change(self, session_id: str, status: str, message: str = ""):
        """Broadcast status change event"""
        await self.send_event(session_id, {
            "event": "status_changed",
            "status": status,
            "message": message
        })
    
    async def broadcast_field_extracted(self, session_id: str, field_id: str, value: str, label: str = ""):
        """Broadcast field extraction event"""
        await self.send_event(session_id, {
            "event": "field_extracted",
            "field_id": field_id,
            "value": value,
            "label": label
        })
    
    async def broadcast_captcha_detected(self, session_id: str, screenshot_b64: str):
        """Broadcast CAPTCHA detection event"""
        await self.send_event(session_id, {
            "event": "captcha_detected",
            "screenshot_b64": screenshot_b64
        })
    
    async def broadcast_error(self, session_id: str, error_message: str):
        """Broadcast error event"""
        await self.send_event(session_id, {
            "event": "error",
            "message": error_message
        })


# Global connection manager instance
manager = ConnectionManager()


# CHANGE 3: Global broadcast function for executor
async def broadcast_event(session_id: str, event: dict):
    """Send event to all WebSocket clients watching this session"""
    await manager.send_event(session_id, event)


async def websocket_endpoint(websocket: WebSocket, session_id: str):
    """WebSocket endpoint handler"""
    await manager.connect(websocket, session_id)
    
    try:
        # Keep connection alive and listen for client messages
        while True:
            # Wait for any message from client (heartbeat, etc.)
            data = await websocket.receive_text()
            
            # Echo back or handle client commands if needed
            if data == "ping":
                await websocket.send_text(json.dumps({"event": "pong"}))
    
    except WebSocketDisconnect:
        manager.disconnect(websocket, session_id)
    except Exception as e:
        print(f"[WebSocket] Error: {e}")
        manager.disconnect(websocket, session_id)
