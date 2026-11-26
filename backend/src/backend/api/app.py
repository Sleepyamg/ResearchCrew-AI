"""FastAPI layer around the existing ResearchCrew.

Run with ``uv run serve`` (or ``uv run uvicorn backend.api.app:app``) from the
``backend`` directory.
"""

from __future__ import annotations

import asyncio
import json
import os
from typing import AsyncIterator

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, field_validator

load_dotenv()
# The CLI asks interactively about CrewAI traces; a background API worker
# cannot answer that prompt. Default to no tracing unless .env enables it.
os.environ.setdefault("CREWAI_TRACING_ENABLED", "false")

from backend.services.event_tracker import register_listener  # noqa: E402
from backend.services.research_runner import start_research  # noqa: E402
from backend.services.session_store import store  # noqa: E402

MAX_TOPIC_LENGTH = 2000
SSE_POLL_SECONDS = 0.4
SSE_HEARTBEAT_SECONDS = 15

app = FastAPI(title="ResearchCrew AI API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv(
        "CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173"
    ).split(","),
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type", "Last-Event-ID"],
)

register_listener()


class ResearchRequest(BaseModel):
    topic: str = Field(..., max_length=MAX_TOPIC_LENGTH)

    @field_validator("topic")
    @classmethod
    def not_blank(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Research topic cannot be empty.")
        return value


@app.get("/api/health")
def health() -> dict:
    active = store.active
    return {
        "status": "ok",
        "model_configured": bool(os.getenv("MODEL")),
        "api_key_configured": bool(os.getenv("OPENROUTER_API_KEY")),
        "active_session": active.id if active else None,
    }


@app.post("/api/research", status_code=202)
def create_research(request: ResearchRequest) -> dict:
    session = store.create_if_idle(request.topic)
    if session is None:
        raise HTTPException(
            status_code=409,
            detail="A research session is already running. Wait for it to finish.",
        )
    start_research(session)
    return session.snapshot(include_events=False)


@app.get("/api/research/{session_id}")
def get_research(session_id: str) -> dict:
    session = store.get(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Research session not found.")
    return session.snapshot()


@app.get("/api/research/{session_id}/events")
async def stream_events(session_id: str, request: Request) -> StreamingResponse:
    session = store.get(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Research session not found.")

    # Replay from the beginning, or from Last-Event-ID after a reconnect.
    try:
        last_id = int(request.headers.get("last-event-id", "0"))
    except ValueError:
        last_id = 0

    async def event_source() -> AsyncIterator[str]:
        nonlocal last_id
        idle = 0.0
        yield "retry: 3000\n\n"
        while True:
            if await request.is_disconnected():
                return
            pending = session.events_after(last_id)
            for event in pending:
                last_id = event["id"]
                yield f"id: {event['id']}\nevent: activity\ndata: {json.dumps(event)}\n\n"
            if pending:
                idle = 0.0
            if session.finished and not session.events_after(last_id):
                payload = json.dumps(session.snapshot(include_events=False))
                yield f"event: done\ndata: {payload}\n\n"
                return
            await asyncio.sleep(SSE_POLL_SECONDS)
            idle += SSE_POLL_SECONDS
            if idle >= SSE_HEARTBEAT_SECONDS:
                idle = 0.0
                yield ": keep-alive\n\n"

    return StreamingResponse(
        event_source(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


def serve() -> None:
    """Entry point for ``uv run serve``. Binds to localhost by default."""
    import uvicorn

    uvicorn.run(
        "backend.api.app:app",
        host=os.getenv("API_HOST", "127.0.0.1"),
        port=int(os.getenv("API_PORT", "8000")),
    )
