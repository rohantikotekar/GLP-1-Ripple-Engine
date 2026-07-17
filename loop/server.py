import asyncio
import os
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

# Repo-root .env (NEXLA_*, AKASH_MODEL_*, STATE_PATH, …) — must load before
# the loop imports anything that reads os.environ at call time.
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

from loop import state as st, engine

app = FastAPI(title="GLP-1 Ripple Engine")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
)

# The P4 dashboard, served from the same origin as the API.
FRONTEND = os.path.join(os.path.dirname(os.path.dirname(__file__)), "frontend", "index.html")

_state = st.load()
_pending = []  # injected catalysts, FIFO


@app.get("/")
def dashboard():
    # One public URL: the Akash lease serves this dashboard, which polls /state
    # on the same origin — no CORS, no mixed-content. If the file isn't shipped
    # in the image, fall through to a hint instead of a 500.
    if os.path.exists(FRONTEND):
        return FileResponse(FRONTEND)
    return {"service": "GLP-1 Ripple Engine", "hint": "frontend/index.html not bundled; GET /state for data"}


@app.get("/state")
def get_state():
    return _state


@app.post("/inject")
def inject(catalyst: dict):  # data/injector.py or the UI can POST here
    _pending.append(catalyst)
    return {"queued": len(_pending)}


@app.post("/reset")
def reset():
    global _state, _pending
    _state = st.init_state()
    _pending = []
    st.save(_state)
    return {"ok": True}


@app.on_event("startup")
async def loop_task():
    async def run():
        global _state
        while True:
            await asyncio.sleep(3)
            if _state["status"] == "stopped":
                continue
            cat = _pending.pop(0) if _pending else None
            # Feed sense (Nexla HTTP + yfinance) is blocking — keep the event
            # loop free so GET /state stays snappy during a slow pull.
            _state = await asyncio.to_thread(engine.tick, _state, cat)
            st.save(_state)

    asyncio.create_task(run())
