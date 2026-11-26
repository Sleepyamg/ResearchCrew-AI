"""Runs the existing ResearchCrew in a background thread for one session."""

from __future__ import annotations

import threading
from datetime import date

from backend.services.errors import SHORT_REASONS, classify_error
from backend.services.event_tracker import current_session_id
from backend.services.session_store import ResearchSession, utc_now


def _run(session: ResearchSession) -> None:
    current_session_id.set(session.id)
    session.status = "running"
    session.add_event("session_started", "Research session started", detail=session.topic)

    try:
        # Imported lazily so the API can start (and report health) even if the
        # LLM environment variables are missing.
        from backend.crew import ResearchCrew

        result = ResearchCrew().crew().kickoff(
            inputs={"topic": session.topic, "current_date": date.today().isoformat()}
        )
        report = (getattr(result, "raw", None) or str(result or "")).strip()

        if not report:
            raise RuntimeError("The crew finished without producing a report.")

        session.report = report
        session.status = "completed"
        session.completed_at = utc_now()
        session.add_event("session_completed", "Research execution completed")
    except Exception as error:  # noqa: BLE001 - surface every failure to the UI
        session.error = classify_error(error)
        session.fail_active_agents(f"Stopped: {SHORT_REASONS[session.error['kind']]}")
        session.status = "failed"
        session.completed_at = utc_now()
        session.add_event(
            # Full technical detail lives only in session.error (report panel).
            "session_failed", session.error["message"], level="error",
        )


def start_research(session: ResearchSession) -> None:
    thread = threading.Thread(
        target=_run, args=(session,), name=f"research-{session.id[:8]}", daemon=True
    )
    thread.start()
