import { useEffect, useMemo, useRef } from "react";
import type { ActivityEvent, AgentKey } from "../types/research";

const AGENT_SHORT: Record<AgentKey, string> = {
  research_manager: "Manager",
  researcher: "Researcher",
  fact_checker: "Fact Checker",
  report_writer: "Writer",
};

function elapsed(start: string, at: string): string {
  const seconds = Math.max(0, Math.round((Date.parse(at) - Date.parse(start)) / 1000));
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return `${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
}

export type StreamState = "idle" | "live" | "reconnecting";

interface Props {
  events: ActivityEvent[];
  startedAt: string | null;
  connection: StreamState;
}

export function ActivityLog({ events, startedAt, connection }: Props) {
  const listRef = useRef<HTMLOListElement>(null);
  const stick = useRef(true);

  // Plain agent_status updates are already shown in the agent panel, so the
  // log keeps actions and lifecycle milestones. Ordered by CrewAI's emission
  // sequence because handler threads may deliver events slightly out of order.
  const visible = useMemo(
    () =>
      events
        .filter((e) => e.type !== "agent_status" || e.detail === "failed")
        .sort((a, b) => a.seq - b.seq || a.id - b.id),
    [events],
  );

  useEffect(() => {
    const el = listRef.current;
    if (el && stick.current) el.scrollTop = el.scrollHeight;
  }, [visible.length]);

  const onScroll = () => {
    const el = listRef.current;
    if (el) stick.current = el.scrollHeight - el.scrollTop - el.clientHeight < 40;
  };

  return (
    <section className="panel panel-log">
      <div className="panel-head">
        <h2 className="section-title">Live activity</h2>
        {connection !== "idle" ? (
          <span className={`conn conn-${connection === "live" ? "online" : "warn"}`}>
            <span className="dot" aria-hidden="true" />
            {connection === "live" ? "Streaming" : "Reconnecting…"}
          </span>
        ) : null}
      </div>
      {visible.length === 0 ? (
        <p className="empty">Activity from the research crew will appear here.</p>
      ) : (
        <ol className="log" ref={listRef} onScroll={onScroll} aria-live="polite">
          {visible.map((event) => (
            <li key={event.id} className={`log-item log-${event.level}`}>
              <span className="log-time">{startedAt ? elapsed(startedAt, event.timestamp) : ""}</span>
              <div className="log-body">
                <div className="log-line">
                  {event.agent ? <span className="tag">{AGENT_SHORT[event.agent]}</span> : null}
                  <span className="log-msg">{event.message}</span>
                </div>
                {event.detail && event.type !== "agent_status" ? <p className="log-detail">{event.detail}</p> : null}
              </div>
            </li>
          ))}
        </ol>
      )}
    </section>
  );
}
