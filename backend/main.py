"""
Chaos Chess — FastAPI server.

Endpoints:
  GET  /             → serves frontend/index.html
  GET  /health       → health check
  WS   /ws           → WebSocket game session
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path

import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware

from engine import ChaosChessEngine
from rule_manager import update_rules_with_llm, update_rules_simple

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("chaos-chess")

# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------
app = FastAPI(title="Chaos Chess", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

FRONTEND_DIR = Path(__file__).parent.parent / "frontend"

# ---------------------------------------------------------------------------
# HTTP routes
# ---------------------------------------------------------------------------

@app.get("/")
async def serve_frontend() -> FileResponse:
    return FileResponse(FRONTEND_DIR / "index.html")


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}


# ---------------------------------------------------------------------------
# WebSocket endpoint
# ---------------------------------------------------------------------------

@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket) -> None:
    await ws.accept()
    engine = ChaosChessEngine()
    logger.info("New WebSocket connection opened.")

    try:
        while True:
            raw = await ws.receive_text()
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                await _send_error(ws, "Invalid JSON")
                continue

            action = data.get("action", "")
            logger.info("Action received: %s", action)

            # ----------------------------------------------------------------
            if action == "start_game":
                max_changes = int(data.get("max_rule_changes", 3))
                engine.start_game(max_changes)
                status = engine.get_status()
                await ws.send_text(json.dumps({
                    "type": "game_started",
                    **status,
                }))

            # ----------------------------------------------------------------
            elif action == "move":
                uci = data.get("move", "")
                ok, err = engine.validate_move(uci)
                if not ok:
                    await _send_error(ws, err)
                    continue
                status = engine.apply_move(uci)
                await ws.send_text(json.dumps({
                    "type": "move_applied",
                    **status,
                }))

            # ----------------------------------------------------------------
            elif action == "rule_change":
                if not engine.can_change_rules():
                    await _send_error(ws, "No more rule changes allowed.")
                    continue

                user_request: str = data.get("request", "")
                groq_key = os.getenv("GROQ_API_KEY", "")
                openai_key = os.getenv("OPENAI_API_KEY", "")

                if groq_key or openai_key:
                    try:
                        new_rules = await update_rules_with_llm(engine.rules, user_request)
                    except Exception as exc:
                        logger.warning("LLM call failed (%s), falling back to simple parser.", exc)
                        new_rules = update_rules_simple(engine.rules, user_request)
                else:
                    logger.info("No API key configured — using simple keyword parser.")
                    new_rules = update_rules_simple(engine.rules, user_request)

                success, msg = engine.update_rules(new_rules)
                if not success:
                    await _send_error(ws, msg)
                    continue

                status = engine.get_status()
                await ws.send_text(json.dumps({
                    "type": "rules_updated",
                    "message": msg,
                    **status,
                }))

            # ----------------------------------------------------------------
            elif action == "get_status":
                status = engine.get_status()
                await ws.send_text(json.dumps({
                    "type": "status",
                    **status,
                }))

            # ----------------------------------------------------------------
            else:
                await _send_error(ws, f"Unknown action: {action!r}")

    except WebSocketDisconnect:
        logger.info("WebSocket connection closed.")
    except Exception as exc:
        logger.exception("Unhandled error in WebSocket handler: %s", exc)
        try:
            await _send_error(ws, "Internal server error.")
        except Exception:
            pass


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _send_error(ws: WebSocket, message: str) -> None:
    await ws.send_text(json.dumps({"type": "error", "message": message}))


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=False)
