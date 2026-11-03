from typing import Dict, List, Set
from fastapi import WebSocket


class ConnectionManager:
    """
    Manages active WebSocket client connections organized by conversation_id and user_id.
    Supports both conversation-level rooms and user-level global notification streams.
    """

    def __init__(self):
        # Maps conversation_id (str) -> List[WebSocket]
        self.conversations: Dict[str, List[WebSocket]] = {}
        # Maps user_id (str) -> List[WebSocket] (for personal/sidebar real-time notifications)
        self.user_sockets: Dict[str, List[WebSocket]] = {}

    async def connect(self, conversation_id: str, user_id: str, websocket: WebSocket):
        await websocket.accept()

        if conversation_id not in self.conversations:
            self.conversations[conversation_id] = []
        if websocket not in self.conversations[conversation_id]:
            self.conversations[conversation_id].append(websocket)

        if user_id not in self.user_sockets:
            self.user_sockets[user_id] = []
        if websocket not in self.user_sockets[user_id]:
            self.user_sockets[user_id].append(websocket)

    async def connect_user(self, user_id: str, websocket: WebSocket):
        """Connects a user-level WebSocket for sidebar and global real-time updates."""
        await websocket.accept()
        if user_id not in self.user_sockets:
            self.user_sockets[user_id] = []
        if websocket not in self.user_sockets[user_id]:
            self.user_sockets[user_id].append(websocket)

    def disconnect(self, conversation_id: str, user_id: str, websocket: WebSocket):
        if conversation_id in self.conversations:
            if websocket in self.conversations[conversation_id]:
                self.conversations[conversation_id].remove(websocket)
            if not self.conversations[conversation_id]:
                del self.conversations[conversation_id]

        if user_id in self.user_sockets:
            if websocket in self.user_sockets[user_id]:
                self.user_sockets[user_id].remove(websocket)
            if not self.user_sockets[user_id]:
                del self.user_sockets[user_id]

    def disconnect_user(self, user_id: str, websocket: WebSocket):
        if user_id in self.user_sockets:
            if websocket in self.user_sockets[user_id]:
                self.user_sockets[user_id].remove(websocket)
            if not self.user_sockets[user_id]:
                del self.user_sockets[user_id]

    async def broadcast_to_conversation(
        self,
        conversation_id: str,
        payload: dict,
        participant_user_ids: List[str] | None = None,
    ):
        """
        Sends a JSON payload to all active sockets in the conversation room
        AND any user-level sockets belonging to the conversation's participants.
        """
        target_sockets: Set[WebSocket] = set()

        if conversation_id in self.conversations:
            for ws in self.conversations[conversation_id]:
                target_sockets.add(ws)

        if participant_user_ids:
            for uid in participant_user_ids:
                for ws in self.user_sockets.get(str(uid), []):
                    target_sockets.add(ws)

        dead_connections: List[WebSocket] = []
        for connection in list(target_sockets):
            try:
                await connection.send_json(payload)
            except Exception:
                dead_connections.append(connection)

        # Cleanup any dead connections
        for dead in dead_connections:
            if conversation_id in self.conversations and dead in self.conversations[conversation_id]:
                self.conversations[conversation_id].remove(dead)
            for uid, sockets in list(self.user_sockets.items()):
                if dead in sockets:
                    sockets.remove(dead)


ws_manager = ConnectionManager()
