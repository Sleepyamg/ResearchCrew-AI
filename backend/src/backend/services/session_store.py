"""In-memory research session storage.

Sessions live only for the lifetime of the API process. Each session keeps an
append-only list of normalized events so that SSE clients connecting late (or
reconnecting) can replay everything from the beginning.
"""

from __future__ import annotations

import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

AGENT_KEYS = ("research_manager", "researcher", "fact_checker", "report_writer")

TERMINAL_STATUSES = {"completed", "failed"}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass
class AgentState:
    status: str = "pending"  # pending | working | coordinating | completed | failed
    activity: str | None = None
    runs: int = 0
    last_seq: float = -1

    def to_dict(self) -> dict[str, Any]:
        return {"status": self.status, "activity": self.activity, "runs": self.runs}


@dataclass
class ResearchSession:
    topic: str
    id: str = field(default_factory=lambda: uuid.uuid4().hex)
    status: str = "queued"  # queued | running | completed | failed
    started_at: str = field(default_factory=utc_now)
    completed_at: str | None = None
    report: str | None = None
    error: dict[str, str] | None = None
    agents: dict[str, AgentState] = field(
        default_factory=lambda: {key: AgentState() for key in AGENT_KEYS}
    )
    events: list[dict[str, Any]] = field(default_factory=list)
    lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    # ---- mutation helpers (thread-safe) ----

    def add_event(
        self,
        type: str,
        message: str,
        agent: str | None = None,
        tool: str | None = None,
        detail: str | None = None,
        level: str = "info",
        seq: float | None = None,
        timestamp: str | None = None,
        include_agents: bool = False,
    ) -> dict[str, Any]:
        with self.lock:
            event_id = len(self.events) + 1
            event = {
                "id": event_id,
                # Ordering key: CrewAI's emission sequence when available.
                "seq": seq if seq is not None else self._next_local_seq(),
                "type": type,
                "agent": agent,
                "tool": tool,
                "message": message,
                "detail": detail,
                "level": level,
                "timestamp": timestamp or utc_now(),
            }
            if include_agents:
                event["agents"] = {k: v.to_dict() for k, v in self.agents.items()}
            self.events.append(event)
            return event

    def set_agent(
        self, key: str | None, status: str, activity: str | None = None,
        new_run: bool = False,
        seq: float | None = None,
        timestamp: str | None = None,
    ) -> None:
        if key not in self.agents:
            return
        with self.lock:
            state = self.agents[key]
            # CrewAI runs sync handlers in a thread pool, so updates can arrive
            # slightly out of order. Ignore anything older than what we have.
            if seq is not None and seq < state.last_seq:
                return
            if seq is not None:
                state.last_seq = seq
            state.status = status
            state.activity = activity
            if new_run:
                state.runs += 1
        self.add_event("agent_status", activity or status, agent=key, detail=status,
                       seq=seq, timestamp=timestamp, include_agents=True)

    def _next_local_seq(self) -> float:
        # Events created outside CrewAI (session start/end) are ordered after the
        # latest known sequence number.
        if not self.events:
            return 0
        return max(e["seq"] for e in self.events[-20:]) + 0.001

    def fail_active_agents(self, reason: str) -> None:
        for key, state in self.agents.items():
            if state.status in ("working", "coordinating"):
                self.set_agent(key, "failed", reason)

    def snapshot(self, include_events: bool = True) -> dict[str, Any]:
        with self.lock:
            data: dict[str, Any] = {
                "id": self.id,
                "topic": self.topic,
                "status": self.status,
                "started_at": self.started_at,
                "completed_at": self.completed_at,
                "report": self.report,
                "error": self.error,
                "agents": {k: v.to_dict() for k, v in self.agents.items()},
            }
            if include_events:
                data["events"] = list(self.events)
            return data

    def events_after(self, last_id: int) -> list[dict[str, Any]]:
        with self.lock:
            return self.events[last_id:]

    @property
    def finished(self) -> bool:
        return self.status in TERMINAL_STATUSES


class SessionStore:
    """Holds all sessions and enforces a single active research run."""

    def __init__(self) -> None:
        self._sessions: dict[str, ResearchSession] = {}
        self._lock = threading.Lock()
        self._active_id: str | None = None

    def create_if_idle(self, topic: str) -> ResearchSession | None:
        """Create a session unless another one is still running."""
        with self._lock:
            active = self._sessions.get(self._active_id or "")
            if active is not None and not active.finished:
                return None
            session = ResearchSession(topic=topic)
            self._sessions[session.id] = session
            self._active_id = session.id
            return session

    def get(self, session_id: str) -> ResearchSession | None:
        return self._sessions.get(session_id)

    @property
    def active(self) -> ResearchSession | None:
        session = self._sessions.get(self._active_id or "")
        if session is not None and not session.finished:
            return session
        return None


store = SessionStore()
