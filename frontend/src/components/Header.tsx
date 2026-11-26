import { ExternalLink } from "lucide-react";

export type BackendState = "checking" | "online" | "offline";

const REPO_URL = "https://github.com/Sleepyamg/ResearchCrew-AI";

export function Header({ backend, modelReady }: { backend: BackendState; modelReady: boolean }) {
  const label =
    backend === "checking"
      ? "Checking backend"
      : backend === "offline"
        ? "Backend offline"
        : modelReady
          ? "Backend connected"
          : "Backend connected · LLM not configured";

  const tone = backend === "online" && !modelReady ? "warn" : backend;

  return (
    <header className="header">
      <div className="header-inner">
        <div className="brand">
          <span className="brand-mark" aria-hidden="true">R</span>
          <span className="brand-name">ResearchCrew AI</span>
        </div>
        <div className="header-meta">
          <span className={`conn conn-${tone}`} title={label}>
            <span className="dot" aria-hidden="true" />
            <span className="conn-label">{label}</span>
          </span>
          <a className="icon-link" href={REPO_URL} target="_blank" rel="noreferrer">
            GitHub <ExternalLink size={13} />
          </a>
        </div>
      </div>
    </header>
  );
}
