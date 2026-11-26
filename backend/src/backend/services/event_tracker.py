"""Translate CrewAI event-bus events into small, UI-friendly session events.

Uses the supported CrewAI (1.x) event bus: ``BaseEventListener`` plus
``crewai_event_bus.on(...)``. The listener is registered exactly once per
process. Each event is routed to the research session that produced it via a
``ContextVar`` set in the worker thread (CrewAI copies the emitting thread's
context into its handler threads); if the context is missing, the single
active session is used as a fallback.

Only short, non-sensitive summaries are recorded: search queries, source
domains, tool outcomes and lifecycle transitions. Prompts, raw tool output,
LLM messages and model reasoning are never forwarded.
"""

from __future__ import annotations

import json
import threading
from contextvars import ContextVar
from typing import Any
from urllib.parse import urlparse

from crewai.events import BaseEventListener
from crewai.events.types.agent_events import (
    AgentExecutionCompletedEvent,
    AgentExecutionErrorEvent,
    AgentExecutionStartedEvent,
)
from crewai.events.types.crew_events import (
    CrewKickoffCompletedEvent,
    CrewKickoffFailedEvent,
    CrewKickoffStartedEvent,
)
from crewai.events.types.llm_events import LLMCallFailedEvent
from crewai.events.types.task_events import (
    TaskCompletedEvent,
    TaskFailedEvent,
    TaskStartedEvent,
)
from crewai.events.types.tool_usage_events import (
    ToolUsageErrorEvent,
    ToolUsageFinishedEvent,
    ToolUsageStartedEvent,
)

from backend.services.errors import redact, short_reason
from backend.services.session_store import ResearchSession, store

current_session_id: ContextVar[str | None] = ContextVar(
    "research_session_id", default=None
)

# Agent roles come from config/agents.yaml. Matching on role keywords keeps the
# mapping working if the YAML wording is slightly adjusted.
_ROLE_KEYWORDS = (
    ("research_manager", ("director", "manager")),
    ("fact_checker", ("verification", "fact")),
    ("report_writer", ("writer", "report")),
    ("researcher", ("research analyst", "researcher", "analyst")),
)

AGENT_LABELS = {
    "research_manager": "Research Manager",
    "researcher": "Researcher",
    "fact_checker": "Fact Checker",
    "report_writer": "Report Writer",
}

TASK_LABELS = {
    "research_task": "Research task",
    "verification_task": "Verification task",
    "report_task": "Report task",
}


def agent_key_from_role(role: str | None) -> str | None:
    if not role:
        return None
    text = " ".join(role.lower().split())
    for key, keywords in _ROLE_KEYWORDS:
        if any(word in text for word in keywords):
            return key
    return None


def _role_of(event: Any) -> str | None:
    agent = getattr(event, "agent", None)
    role = getattr(agent, "role", None) if agent is not None else None
    return role or getattr(event, "agent_role", None)


def _domain(url: str | None) -> str | None:
    if not url:
        return None
    try:
        host = urlparse(str(url).strip()).hostname
    except ValueError:
        return None
    return host.removeprefix("www.") if host else None


def _short(text: Any, limit: int = 160) -> str:
    value = redact(" ".join(str(text).split()))
    return value if len(value) <= limit else value[: limit - 1] + "…"


def _args(event: Any) -> dict[str, Any]:
    args = getattr(event, "tool_args", None)
    if isinstance(args, dict):
        return args
    if isinstance(args, str):
        try:
            parsed = json.loads(args)
            return parsed if isinstance(parsed, dict) else {}
        except ValueError:
            return {}
    return {}


def _task_label(event: Any) -> str:
    task = getattr(event, "task", None)
    name = getattr(event, "task_name", None) or getattr(task, "name", None)
    if name and name in TASK_LABELS:
        return TASK_LABELS[name]
    if name:
        return _short(name, 60)
    return "Task"


def _meta(event: Any) -> dict[str, Any]:
    seq = getattr(event, "emission_sequence", None)
    ts = getattr(event, "timestamp", None)
    return {
        "seq": float(seq) if seq is not None else None,
        "timestamp": ts.isoformat() if ts is not None else None,
    }


def _emit(session: ResearchSession, event: Any, *args: Any, **kwargs: Any) -> None:
    session.add_event(*args, **kwargs, **_meta(event))


def _set(session: ResearchSession, event: Any, *args: Any, **kwargs: Any) -> None:
    session.set_agent(*args, **kwargs, **_meta(event))


def _resolve_session() -> ResearchSession | None:
    session_id = current_session_id.get()
    if session_id:
        return store.get(session_id)
    return store.active


def _tool_kind(name: str) -> str:
    lowered = (name or "").lower()
    if "delegate" in lowered:
        return "delegate"
    if "ask question" in lowered:
        return "ask"
    if "search" in lowered:
        return "search"
    if "scrap" in lowered:
        return "scrape"
    return "other"


class ResearchEventListener(BaseEventListener):
    """Registers handlers on the CrewAI event bus (instantiate once)."""

    def setup_listeners(self, bus: Any) -> None:  # noqa: C901 - flat handler list
        @bus.on(CrewKickoffStartedEvent)
        def on_crew_started(source: Any, event: CrewKickoffStartedEvent) -> None:
            session = _resolve_session()
            if session:
                _emit(session, event, "crew_started", "Crew execution started")

        @bus.on(CrewKickoffCompletedEvent)
        def on_crew_completed(source: Any, event: CrewKickoffCompletedEvent) -> None:
            session = _resolve_session()
            if session:
                _emit(session, event, "crew_completed", "Crew execution finished")

        @bus.on(CrewKickoffFailedEvent)
        def on_crew_failed(source: Any, event: CrewKickoffFailedEvent) -> None:
            session = _resolve_session()
            if session:
                _emit(
                    session, event,
                    "crew_failed", f"Crew execution failed: {short_reason(event.error)}",
                    level="error",
                )

        @bus.on(TaskStartedEvent)
        def on_task_started(source: Any, event: TaskStartedEvent) -> None:
            session = _resolve_session()
            if session:
                _emit(session, event, "task_started", f"{_task_label(event)} started")

        @bus.on(TaskCompletedEvent)
        def on_task_completed(source: Any, event: TaskCompletedEvent) -> None:
            session = _resolve_session()
            if session:
                _emit(session, event, "task_completed", f"{_task_label(event)} completed")

        @bus.on(TaskFailedEvent)
        def on_task_failed(source: Any, event: TaskFailedEvent) -> None:
            session = _resolve_session()
            if session:
                _emit(
                    session, event,
                    "task_failed",
                    f"{_task_label(event)} failed: {short_reason(event.error)}",
                    level="error",
                )

        @bus.on(AgentExecutionStartedEvent)
        def on_agent_started(source: Any, event: AgentExecutionStartedEvent) -> None:
            session = _resolve_session()
            key = agent_key_from_role(_role_of(event))
            if not session or not key:
                return
            if key == "research_manager":
                _set(session, event, key, "coordinating",
                                  f"Coordinating: {_task_label(event)}", new_run=True)
            else:
                _set(session, event, key, "working",
                                  "Working on delegated assignment", new_run=True)

        @bus.on(AgentExecutionCompletedEvent)
        def on_agent_completed(source: Any, event: AgentExecutionCompletedEvent) -> None:
            session = _resolve_session()
            key = agent_key_from_role(_role_of(event))
            if not session or not key:
                return
            if key == "research_manager":
                _set(session, event, key, "completed",
                                  f"Finished coordinating: {_task_label(event)}")
            else:
                _set(session, event, key, "completed",
                                  "Returned results to Research Manager")

        @bus.on(AgentExecutionErrorEvent)
        def on_agent_error(source: Any, event: AgentExecutionErrorEvent) -> None:
            session = _resolve_session()
            key = agent_key_from_role(_role_of(event))
            if session and key:
                _set(session, event, key, "failed", f"Stopped: {short_reason(event.error)}")

        @bus.on(ToolUsageStartedEvent)
        def on_tool_started(source: Any, event: ToolUsageStartedEvent) -> None:
            session = _resolve_session()
            if not session:
                return
            key = agent_key_from_role(_role_of(event))
            args = _args(event)
            kind = _tool_kind(event.tool_name)

            if kind in ("delegate", "ask"):
                coworker = args.get("coworker") or args.get("co_worker") or ""
                target = agent_key_from_role(str(coworker))
                target_label = AGENT_LABELS.get(target or "", _short(coworker, 60) or "coworker")
                verb = "delegated work to" if kind == "delegate" else "asked a question to"
                task_text = args.get("task") or args.get("question")
                _emit(
                    session, event,
                    "delegation", f"Research Manager {verb} {target_label}",
                    agent=key or "research_manager", tool=event.tool_name,
                    detail=_short(task_text, 220) if task_text else None,
                )
                if key:
                    _set(session, event, key, "coordinating", f"Waiting on {target_label}")
                return

            if kind == "search":
                query = args.get("query")
                message = f'Searching: "{_short(query, 120)}"' if query else "Running web search"
            elif kind == "scrape":
                domain = _domain(args.get("url"))
                message = f"Reading {domain}" if domain else "Extracting webpage content"
            else:
                message = f"Using tool: {event.tool_name}"

            _emit(session, event, "tool_started", message, agent=key, tool=event.tool_name)
            if key and key != "research_manager":
                _set(session, event, key, "working", message)

        @bus.on(ToolUsageFinishedEvent)
        def on_tool_finished(source: Any, event: ToolUsageFinishedEvent) -> None:
            session = _resolve_session()
            if not session:
                return
            key = agent_key_from_role(_role_of(event))
            kind = _tool_kind(event.tool_name)
            message, level, detail = _summarize_tool_output(kind, event)
            if kind in ("delegate", "ask") and key:
                _set(session, event, key, "coordinating", "Reviewing delegated results")
            if message:
                _emit(session, event, "tool_finished", message, agent=key,
                                  tool=event.tool_name, detail=detail, level=level)

        @bus.on(ToolUsageErrorEvent)
        def on_tool_error(source: Any, event: ToolUsageErrorEvent) -> None:
            session = _resolve_session()
            if session:
                _emit(
                    session, event,
                    "tool_error", f"{event.tool_name} failed",
                    agent=agent_key_from_role(_role_of(event)),
                    tool=event.tool_name, detail=_short(event.error, 200),
                    level="warning",
                )

        @bus.on(LLMCallFailedEvent)
        def on_llm_failed(source: Any, event: LLMCallFailedEvent) -> None:
            session = _resolve_session()
            if session:
                _emit(
                    session, event,
                    "llm_error", f"Language model call failed: {short_reason(event.error)}",
                    agent=agent_key_from_role(_role_of(event)),
                    level="warning",
                )


def _summarize_tool_output(kind: str, event: Any) -> tuple[str | None, str, str | None]:
    """Return (message, level, detail) without exposing raw page content."""
    output = getattr(event, "output", None)
    parsed: Any = None
    if isinstance(output, str):
        try:
            parsed = json.loads(output)
        except ValueError:
            parsed = None

    if kind == "search":
        if isinstance(parsed, list):
            domains = []
            for item in parsed:
                domain = _domain(item.get("url")) if isinstance(item, dict) else None
                if domain and domain not in domains:
                    domains.append(domain)
            return (f"Search returned {len(parsed)} results", "info",
                    ", ".join(domains[:6]) or None)
        if isinstance(parsed, dict) and parsed.get("status") == "error":
            return "Search failed", "warning", _short(parsed.get("message", ""), 200)
        return "Search finished", "info", None

    if kind == "scrape":
        if isinstance(parsed, dict):
            domain = _domain(parsed.get("url"))
            if parsed.get("status") == "error":
                return (f"Could not read {domain or 'page'}", "warning",
                        _short(parsed.get("message", ""), 200))
            title = parsed.get("title")
            note = " (truncated)" if parsed.get("truncated") else ""
            return (f"Extracted content from {domain or 'page'}{note}", "info",
                    _short(title, 140) if title else None)
        return "Page extraction finished", "info", None

    if kind in ("delegate", "ask"):
        return "Delegated work returned to Research Manager", "info", None

    return None, "info", None


_registration_lock = threading.Lock()
_listener: ResearchEventListener | None = None


def register_listener() -> None:
    """Register the event listener once per process."""
    global _listener
    with _registration_lock:
        if _listener is None:
            _listener = ResearchEventListener()
