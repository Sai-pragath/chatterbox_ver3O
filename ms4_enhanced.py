from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from datetime import datetime
import uvicorn

app = FastAPI()

class ConnectionManager:
    def __init__(self):
        self.connections = {}  # websocket -> {username, room}

    async def connect(self, websocket: WebSocket, username: str, room: str):
        self.connections[websocket] = {"username": username, "room": room}
        await self.broadcast(room, {
            "type": "system",
            "message": f"{username} joined {room} 👋"
        })

    def disconnect(self, websocket: WebSocket):
        return self.connections.pop(websocket, None)

    async def broadcast(self, room: str, data: dict):
        # We create a list of disconnected sockets to clean up if broadcast fails
        disconnected_ws = []
        for ws, info in self.connections.items():
            if info["room"] == room:
                try:
                    await ws.send_json(data)
                except Exception:
                    disconnected_ws.append(ws)
        
        for ws in disconnected_ws:
            self.disconnect(ws)

manager = ConnectionManager()

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    username = "Unknown"
    room = "general"

    try:
        # Initial connection data
        join_data = await websocket.receive_json()
        username = join_data.get("username", "Anonymous")
        room = join_data.get("room", "general")

        await manager.connect(websocket, username, room)

        while True:
            data = await websocket.receive_json()
            event = data.get("type")

            if event == "chat":
                message_data = {
                    "type": "chat",
                    "username": username,
                    "message": data.get("message", ""),
                    "time": datetime.now().strftime("%I:%M %p")
                }
                
                # Handle Voice Messages
                if "voiceData" in data:
                    message_data["voiceData"] = data["voiceData"]
                    message_data["duration"] = data.get("duration", "0:00")
                
                await manager.broadcast(room, message_data)

            elif event in ["typing", "stop_typing"]:
                await manager.broadcast(room, {
                    "type": event,
                    "username": username
                })

            elif event == "switch_room":
                old_room = room
                room = data.get("room", "general")
                
                # Update the stored room for this connection
                if websocket in manager.connections:
                    manager.connections[websocket]["room"] = room

                await manager.broadcast(old_room, {
                    "type": "system",
                    "message": f"{username} left the room ❌"
                })
                await manager.broadcast(room, {
                    "type": "system",
                    "message": f"{username} joined {room} 👋"
                })

    except WebSocketDisconnect:
        user_info = manager.disconnect(websocket)
        if user_info:
            await manager.broadcast(user_info["room"], {
                "type": "system",
                "message": f"{user_info['username']} disconnected ❌"
            })
    except Exception as e:
        print(f"Server Error: {e}")
        manager.disconnect(websocket)

if __name__ == "__main__":
    # Note: Ensure the filename matches your actual python file name (e.g., main:app)
    uvicorn.run(app, host="0.0.0.0", port=8000)