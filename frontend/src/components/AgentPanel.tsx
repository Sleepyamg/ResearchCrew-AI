import type { AgentKey, AgentMap } from "../types/research";

const AGENTS: { key: AgentKey; name: string; description: string }[] = [
  { key: "research_manager", name: "Research Manager", description: "Plans the work and delegates tasks to the team." },
  { key: "researcher", name: "Researcher", description: "Searches the web and extracts source content." },
  { key: "fact_checker", name: "Fact Checker", description: "Verifies findings and flags unsupported claims." },
  { key: "report_writer", name: "Report Writer", description: "Writes the final Markdown research report." },
];

const STATUS_LABEL = {
  pending: "Pending",
  working: "Working",
  coordinating: "Coordinating",
  completed: "Completed",
  failed: "Failed",
} as const;

export function AgentPanel({ agents }: { agents: AgentMap | null }) {
  return (
    <section className="panel">
      <div className="panel-head">
        <h2 className="section-title">Agents</h2>
      </div>
      <ul className="agent-list">
        {AGENTS.map(({ key, name, description }) => {
          const state = agents?.[key];
          const status = state?.status ?? "pending";
          return (
            <li key={key} className="agent">
              <div className="agent-top">
                <span className="agent-name">{name}</span>
                <span className={`status status-${status}`}>
                  <span className="dot" aria-hidden="true" />
                  {STATUS_LABEL[status]}
                  {state && state.runs > 1 ? <span className="runs"> · run {state.runs}</span> : null}
                </span>
              </div>
              <p className="agent-desc">{description}</p>
              {state?.activity && status !== "pending" ? <p className="agent-activity">{state.activity}</p> : null}
            </li>
          );
        })}
      </ul>
    </section>
  );
}
