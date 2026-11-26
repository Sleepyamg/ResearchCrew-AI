import type { ActivityEvent, HealthResponse, ResearchSession } from "../types/research";

const BASE = import.meta.env.VITE_API_BASE_URL ?? "";

export class ApiError extends Error {
  constructor(message: string, public status?: number) {
    super(message);
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`${BASE}${path}`, {
      headers: { "Content-Type": "application/json" },
      ...init,
    });
  } catch {
    throw new ApiError("Cannot reach the backend. Is the API server running on port 8000?");
  }

  if (!response.ok) {
    let message = `Request failed (${response.status})`;
    try {
      const body = await response.json();
      if (typeof body.detail === "string") message = body.detail;
      else if (Array.isArray(body.detail) && body.detail[0]?.msg) {
        message = String(body.detail[0].msg).replace(/^Value error, /, "");
      }
    } catch {
      /* keep the generic message */
    }
    throw new ApiError(message, response.status);
  }
  return response.json() as Promise<T>;
}

export const api = {
  health: () => request<HealthResponse>("/api/health"),
  startResearch: (topic: string) =>
    request<ResearchSession>("/api/research", {
      method: "POST",
      body: JSON.stringify({ topic }),
    }),
  getResearch: (id: string) => request<ResearchSession>(`/api/research/${id}`),
};

export interface StreamHandlers {
  onEvent: (event: ActivityEvent) => void;
  onDone: (session: ResearchSession) => void;
  onConnectionChange: (connected: boolean) => void;
}

/**
 * Subscribe to the session's SSE stream. EventSource reconnects on its own and
 * sends Last-Event-ID, so the server resumes from the last delivered event.
 */
export function streamResearch(id: string, handlers: StreamHandlers): () => void {
  const source = new EventSource(`${BASE}/api/research/${id}/events`);

  source.onopen = () => handlers.onConnectionChange(true);
  source.onerror = () => handlers.onConnectionChange(false);

  source.addEventListener("activity", (message) => {
    handlers.onEvent(JSON.parse((message as MessageEvent).data));
  });
  source.addEventListener("done", (message) => {
    source.close();
    handlers.onDone(JSON.parse((message as MessageEvent).data));
  });

  return () => source.close();
}
