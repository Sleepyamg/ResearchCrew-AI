export type AgentKey = "research_manager" | "researcher" | "fact_checker" | "report_writer";

export type AgentStatus = "pending" | "working" | "coordinating" | "completed" | "failed";

export type SessionStatus = "queued" | "running" | "completed" | "failed";

export interface AgentState {
  status: AgentStatus;
  activity: string | null;
  runs: number;
}

export type AgentMap = Record<AgentKey, AgentState>;

export interface ActivityEvent {
  id: number;
  seq: number;
  type: string;
  agent: AgentKey | null;
  tool: string | null;
  message: string;
  detail: string | null;
  level: "info" | "warning" | "error";
  timestamp: string;
  agents?: AgentMap;
}

export interface SessionError {
  kind: string;
  message: string;
  detail: string;
  reset_at?: string | null;
}

export interface ResearchSession {
  id: string;
  topic: string;
  status: SessionStatus;
  started_at: string;
  completed_at: string | null;
  report: string | null;
  error: SessionError | null;
  agents: AgentMap;
  events?: ActivityEvent[];
}

export interface HealthResponse {
  status: string;
  model_configured: boolean;
  api_key_configured: boolean;
  active_session: string | null;
}
