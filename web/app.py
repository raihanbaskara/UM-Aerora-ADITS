"""
================================================================================
AERORA ADITS -- WEB HUB SERVER (FASTAPI + WEBSOCKET)
Robot Seni Tari Indonesia (KRSTI) -- Tim Peneliti Dewantara
================================================================================
"""

import os
import sys
import asyncio
import logging
from typing import Dict, Any, List
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .servo_bridge import bridge
from .motion_service import motion_service
from .voice_ai_bridge import voice_ai_bridge
from .audio_service import audio_service
from .experiment_logger import experiment_logger
from .telemetry_service import get_telemetry

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("WebHub")

app = FastAPI(title="AERORA ADITS Web Hub", version="2.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")
STATIC_DIR = os.path.join(BASE_DIR, "static")

if os.path.exists(STATIC_DIR):
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)

    def disconnect(self, websocket: WebSocket):
        if websocket in self.active_connections:
            self.active_connections.remove(websocket)

    async def broadcast(self, message: Dict[str, Any]):
        for connection in list(self.active_connections):
            try:
                await connection.send_json(message)
            except Exception:
                self.disconnect(connection)

manager = ConnectionManager()

# Background Task untuk Stream WebSocket Broadcast Realtime (10 Hz)
async def state_broadcast_loop():
    while True:
        try:
            if manager.active_connections:
                payload = {
                    "servo_status": bridge.get_system_status(),
                    "servos": bridge.get_all_servos_status(),
                    "motion": motion_service.get_status(),
                    "voice": voice_ai_bridge.get_status(),
                    "audio": audio_service.get_status(),
                    "experiment_log": experiment_logger.get_logs(limit=30),
                    "telemetry": get_telemetry()
                }
                await manager.broadcast(payload)
        except Exception as e:
            logger.error(f"Galat broadcast WebSocket: {e}")
        await asyncio.sleep(0.1)

@app.on_event("startup")
async def startup_event():
    bridge.connect("SIMULATOR")
    asyncio.create_task(state_broadcast_loop())
    logger.info("AERORA ADITS Web Hub berhasil diinisialisasi.")

# ==============================================================================
# ROUTE HALAMAN UTAMA
# ==============================================================================

@app.get("/", response_class=HTMLResponse)
async def get_index():
    index_file = os.path.join(TEMPLATES_DIR, "index.html")
    if os.path.exists(index_file):
        with open(index_file, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    return HTMLResponse("<h2>AERORA ADITS Web Hub: Berkas index.html belum dibuat.</h2>")

# ==============================================================================
# ENDPOINT REST API - STATUS & AUDIO MIKROFON
# ==============================================================================

@app.get("/api/status")
async def get_full_status():
    return {
        "servo_status": bridge.get_system_status(),
        "servos": bridge.get_all_servos_status(),
        "motion": motion_service.get_status(),
        "voice": voice_ai_bridge.get_status(),
        "audio": audio_service.get_status(),
        "experiment_log": experiment_logger.get_logs(limit=50),
        "telemetry": get_telemetry()
    }

@app.get("/api/audio/devices")
async def list_audio_devices():
    return {"devices": audio_service.get_input_devices()}

class SelectAudioRequest(BaseModel):
    index: int

@app.post("/api/audio/select")
async def select_audio_device(req: SelectAudioRequest):
    success, msg = audio_service.select_device(req.index)
    return {"success": success, "message": msg, "audio": audio_service.get_status()}

class ToggleAudioRequest(BaseModel):
    enable: bool = None

@app.post("/api/audio/toggle")
async def toggle_audio_listening(req: ToggleAudioRequest):
    if req.enable is True or (req.enable is None and not audio_service.is_listening):
        success, msg = audio_service.start_listening()
    else:
        success, msg = audio_service.stop_listening()
    return {"success": success, "message": msg, "audio": audio_service.get_status()}

# ==============================================================================
# ENDPOINT REST API - HARDWARE & MOTION
# ==============================================================================

@app.get("/api/ports")
async def list_serial_ports():
    return {"ports": bridge.list_ports()}

class ConnectRequest(BaseModel):
    port: str = "SIMULATOR"
    force_mock: bool = False

@app.post("/api/connect")
async def connect_port(req: ConnectRequest):
    success, msg = bridge.connect(req.port, req.force_mock)
    return {"success": success, "message": msg, "status": bridge.get_system_status()}

@app.post("/api/disconnect")
async def disconnect_port():
    success, msg = bridge.disconnect()
    return {"success": success, "message": msg, "status": bridge.get_system_status()}

@app.get("/api/motions")
async def list_motions():
    return {"files": motion_service.list_motion_files()}

class LoadMotionRequest(BaseModel):
    filename: str

@app.post("/api/motion/load")
async def load_motion(req: LoadMotionRequest):
    success, msg = motion_service.load_motion_file(req.filename)
    return {"success": success, "message": msg, "motion": motion_service.get_status()}

@app.post("/api/motion/play")
async def play_motion():
    success, msg = motion_service.play()
    return {"success": success, "message": msg, "motion": motion_service.get_status()}

@app.post("/api/motion/pause")
async def pause_motion():
    success, msg = motion_service.pause()
    return {"success": success, "message": msg, "motion": motion_service.get_status()}

@app.post("/api/motion/stop")
async def stop_motion():
    success, msg = motion_service.stop()
    return {"success": success, "message": msg, "motion": motion_service.get_status()}

@app.post("/api/motion/step_next")
async def step_next():
    success, msg = motion_service.step_next()
    return {"success": success, "message": msg, "motion": motion_service.get_status()}

@app.post("/api/motion/step_prev")
async def step_prev():
    success, msg = motion_service.step_prev()
    return {"success": success, "message": msg, "motion": motion_service.get_status()}

# ==============================================================================
# ENDPOINT REST API - VOICE AI & EXPERIMENT LOGGING
# ==============================================================================

class VoiceTriggerRequest(BaseModel):
    command: str

@app.post("/api/voice/trigger")
async def trigger_voice(req: VoiceTriggerRequest):
    success, msg = voice_ai_bridge.trigger_command(req.command)
    return {
        "success": success,
        "message": msg,
        "voice": voice_ai_bridge.get_status(),
        "latest_event": experiment_logger.latest_event
    }

@app.get("/api/experiment/logs")
async def get_experiment_logs():
    return experiment_logger.get_logs()

@app.post("/api/experiment/clear")
async def clear_experiment_logs():
    experiment_logger.clear()
    return {"success": True, "message": "Log pengujian berhasil dikosongkan."}

@app.get("/api/experiment/export_csv")
async def export_experiment_csv():
    csv_data = experiment_logger.to_csv_string()
    return Response(
        content=csv_data,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=ADITS_Data_Pengujian_KRSTI.csv"}
    )

# ==============================================================================
# WEBSOCKET REALTIME (STREAM 10 HZ)
# ==============================================================================

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        initial_payload = {
            "servo_status": bridge.get_system_status(),
            "servos": bridge.get_all_servos_status(),
            "motion": motion_service.get_status(),
            "voice": voice_ai_bridge.get_status(),
            "audio": audio_service.get_status(),
            "experiment_log": experiment_logger.get_logs(limit=30),
            "telemetry": get_telemetry()
        }
        await websocket.send_json(initial_payload)

        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception:
        manager.disconnect(websocket)
