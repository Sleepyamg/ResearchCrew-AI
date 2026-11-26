import { useCallback, useEffect, useRef, useState } from "react";
import { ActivityLog, type StreamState } from "./components/ActivityLog";
import { AgentPanel } from "./components/AgentPanel";
import { Header, type BackendState } from "./components/Header";
import { ReportView } from "./components/ReportView";
import { ResearchForm } from "./components/ResearchForm";
import { api, ApiError, streamResearch } from "./services/api";
import type { ActivityEvent, AgentMap, ResearchSession } from "./types/research";

const HEALTH_INTERVAL_MS = 15000;

export default function App() {
  const [backend, setBackend] = useState<BackendState>("checking");
  const [modelReady, setModelReady] = useState(true);
  const [session, setSession] = useState<ResearchSession | null>(null);
  const [agents, setAgents] = useState<AgentMap | null>(null);
  const [events, setEvents] = useState<ActivityEvent[]>([]);
  const [stream, setStream] = useState<StreamState>("idle");
  const [starting, setStarting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const closeStream = useRef<(() => void) | null>(null);
  const seenIds = useRef<Set<number>>(new Set());

  const running = session?.status === "running" || session?.status === "queued";

  const attach = useCallback((initial: ResearchSession) => {
    closeStream.current?.();
    seenIds.current = new Set();
    setSession(initial);
    setAgents(initial.agents);
    setEvents([]);
    setStream("reconnecting");

    closeStream.current = streamResearch(initial.id, {
      onEvent: (event) => {
        if (seenIds.current.has(event.id)) return;
        seenIds.current.add(event.id);
        setEvents((prev) => [...prev, event]);
        if (event.agents) setAgents(event.agents);
        setSession((prev) => (prev && prev.status === "queued" ? { ...prev, status: "running" } : prev));
      },
      onDone: (final) => {
        setSession(final);
        setAgents(final.agents);
        setStream("idle");
        closeStream.current = null;
      },
      onConnectionChange: (connected) => {
        setStream(connected ? "live" : "reconnecting");
        if (!connected) {
          // If the backend restarted, the in-memory session is gone; stop
          // waiting instead of showing a loading state forever.
          api.getResearch(initial.id).catch((error) => {
            if (error instanceof ApiError && error.status === 404) {
              closeStream.current?.();
              closeStream.current = null;
              setStream("idle");
              setSession((prev) =>
                prev
                  ? {
                      ...prev,
                      status: "failed",
                      error: {
                        kind: "session_lost",
                        message: "The backend no longer has this session (it may have restarted).",
                        detail: "",
                      },
                    }
                  : prev,
              );
            }
          });
        }
      },
    });
  }, []);

  // Backend health, plus reattaching to a session that is still running
  // (for example after a page refresh).
  useEffect(() => {
    let cancelled = false;
    let firstCheck = true;
    const check = async () => {
      try {
        const health = await api.health();
        if (cancelled) return;
        setBackend("online");
        setModelReady(health.model_configured && health.api_key_configured);
        if (firstCheck && health.active_session) {
          const active = await api.getResearch(health.active_session);
          if (!cancelled) attach(active);
        }
      } catch {
        if (!cancelled) setBackend("offline");
      } finally {
        firstCheck = false;
      }
    };
    check();
    const timer = setInterval(check, HEALTH_INTERVAL_MS);
    return () => {
      cancelled = true;
      clearInterval(timer);
    };
  }, [attach]);

  useEffect(() => () => closeStream.current?.(), []);

  const start = async (topic: string) => {
    if (starting || running) return;
    setStarting(true);
    setFormError(null);
    try {
      const created = await api.startResearch(topic);
      setBackend("online");
      attach(created);
    } catch (error) {
      setFormError(error instanceof Error ? error.message : "Could not start research.");
      if (error instanceof ApiError && error.status === undefined) setBackend("offline");
    } finally {
      setStarting(false);
    }
  };

  return (
    <>
      <Header backend={backend} modelReady={modelReady} />
      <main className="workspace">
        <div className="col-main">
          <ResearchForm busy={starting || running} disabled={backend === "offline"} error={formError} onSubmit={start} />
          <ReportView session={session} />
        </div>
        <aside className="col-side">
          <AgentPanel agents={agents} />
          <ActivityLog events={events} startedAt={session?.started_at ?? null} connection={stream} />
        </aside>
      </main>
    </>
  );
}
