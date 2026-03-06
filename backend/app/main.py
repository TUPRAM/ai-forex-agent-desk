from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import asyncio
import random
from datetime import datetime, timezone

app = FastAPI(title="AI Forex Agent Desk API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def now_iso():
    return datetime.now(timezone.utc).isoformat()

mock_state = {
    "health": {
        "status": "ok",
        "service": "backend",
        "timestamp": now_iso(),
    },
    "system_summary": {
        "system_status": "online",
        "mode": "read_only",
        "mt5_bridge_status": "disconnected",
        "active_alerts": 2,
        "running_agents": 5,
        "timestamp": now_iso(),
    },
    "account_summary": {
        "account_id": "DEMO-001",
        "broker": "Demo Broker",
        "server": "Demo-Server",
        "balance": 10000.00,
        "equity": 10012.45,
        "margin": 120.30,
        "free_margin": 9892.15,
        "profit": 12.45,
        "currency": "USD",
        "timestamp": now_iso(),
    },
    "positions": [
        {
            "ticket": 1001,
            "symbol": "XAUUSD",
            "type": "buy",
            "volume": 0.10,
            "open_price": 3342.10,
            "current_price": 3343.35,
            "profit": 12.50,
            "status": "open",
        }
    ],
    "orders": [
        {
            "ticket": 2001,
            "symbol": "EURUSD",
            "type": "buy_limit",
            "volume": 0.20,
            "price": 1.08250,
            "status": "pending",
        }
    ],
    "alerts": [
        {
            "id": 1,
            "severity": "warning",
            "message": "MT5 bridge is not connected yet.",
            "timestamp": now_iso(),
        }
    ],
    "agents": [
        {"id": "orchestrator", "name": "Orchestrator", "status": "running", "last_run": now_iso()},
        {"id": "monitoring", "name": "Monitoring Agent", "status": "running", "last_run": now_iso()},
        {"id": "risk", "name": "Risk Manager", "status": "running", "last_run": now_iso()},
        {"id": "reporting", "name": "Reporting Agent", "status": "idle", "last_run": now_iso()},
        {"id": "execution", "name": "Execution Agent", "status": "idle", "last_run": now_iso()},
    ],
    "risk_state": {
        "daily_loss_limit": 300.0,
        "daily_loss_used": 42.5,
        "max_drawdown_limit": 1000.0,
        "current_drawdown": 87.2,
        "kill_switch": False,
        "risk_status": "normal",
        "timestamp": now_iso(),
    },
}

class ConnectionManager:
    def __init__(self):
        self.active_connections = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: dict):
        dead_connections = []
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except Exception:
                dead_connections.append(connection)

        for dead in dead_connections:
            self.disconnect(dead)

manager = ConnectionManager()

@app.get("/api/health")
async def get_health():
    mock_state["health"]["timestamp"] = now_iso()
    return mock_state["health"]

@app.get("/api/system/summary")
async def get_system_summary():
    mock_state["system_summary"]["timestamp"] = now_iso()
    return mock_state["system_summary"]

@app.get("/api/account/summary")
async def get_account_summary():
    mock_state["account_summary"]["timestamp"] = now_iso()
    return mock_state["account_summary"]

@app.get("/api/positions")
async def get_positions():
    return {
        "count": len(mock_state["positions"]),
        "items": mock_state["positions"],
        "timestamp": now_iso(),
    }

@app.get("/api/orders")
async def get_orders():
    return {
        "count": len(mock_state["orders"]),
        "items": mock_state["orders"],
        "timestamp": now_iso(),
    }

@app.get("/api/alerts")
async def get_alerts():
    return {
        "count": len(mock_state["alerts"]),
        "items": mock_state["alerts"],
        "timestamp": now_iso(),
    }

@app.get("/api/agents")
async def get_agents():
    return {
        "count": len(mock_state["agents"]),
        "items": mock_state["agents"],
        "timestamp": now_iso(),
    }

@app.get("/api/risk/state")
async def get_risk_state():
    mock_state["risk_state"]["timestamp"] = now_iso()
    return mock_state["risk_state"]

@app.websocket("/ws/live")
async def websocket_live(websocket: WebSocket):
    await manager.connect(websocket)

    await websocket.send_json({
        "type": "hello",
        "message": "Connected to live stream",
        "timestamp": now_iso(),
    })

    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception:
        manager.disconnect(websocket)

async def fake_live_updates():
    while True:
        delta = round(random.uniform(-8, 8), 2)
        mock_state["account_summary"]["profit"] = round(mock_state["account_summary"]["profit"] + delta, 2)
        mock_state["account_summary"]["equity"] = round(
            mock_state["account_summary"]["balance"] + mock_state["account_summary"]["profit"], 2
        )
        mock_state["account_summary"]["timestamp"] = now_iso()

        if mock_state["positions"]:
            mock_state["positions"][0]["profit"] = mock_state["account_summary"]["profit"]
            mock_state["positions"][0]["current_price"] = round(
                mock_state["positions"][0]["current_price"] + random.uniform(-1.0, 1.0), 2
            )

        agent = random.choice(mock_state["agents"])
        agent["status"] = random.choice(["running", "idle", "warning"])
        agent["last_run"] = now_iso()

        await manager.broadcast({
            "type": "account_update",
            "data": mock_state["account_summary"],
            "timestamp": now_iso(),
        })

        await manager.broadcast({
            "type": "position_update",
            "data": mock_state["positions"],
            "timestamp": now_iso(),
        })

        await manager.broadcast({
            "type": "agent_status_change",
            "data": agent,
            "timestamp": now_iso(),
        })

        await asyncio.sleep(3)

@app.on_event("startup")
async def startup_event():
    asyncio.create_task(fake_live_updates())
