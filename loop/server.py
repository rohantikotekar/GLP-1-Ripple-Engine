import asyncio

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from loop import state as st, engine

app = FastAPI(title="GLP-1 Ripple Engine")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_methods=["*"], allow_headers=["*"],
)

_state = st.load()
_pending = []  # injected catalysts, FIFO


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
            _state = engine.tick(_state, cat)
            st.save(_state)

    asyncio.create_task(run())
