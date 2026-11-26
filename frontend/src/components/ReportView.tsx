import { useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { AlertTriangle, Check, Copy, Download, FileText, Loader2 } from "lucide-react";
import type { ResearchSession } from "../types/research";

function slug(text: string): string {
  return (
    text
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, "-")
      .replace(/^-|-$/g, "")
      .slice(0, 60) || "report"
  );
}

function formatReset(iso: string): string {
  const date = new Date(iso);
  if (Number.isNaN(date.getTime())) return "later";
  const time = date.toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" });
  const minutes = Math.round((date.getTime() - Date.now()) / 60000);
  if (minutes <= 0) return `at ${time}`;
  const relative = minutes < 60 ? `${minutes} min` : `${Math.floor(minutes / 60)} h ${minutes % 60} min`;
  return `at ${time} (in about ${relative})`;
}

export function ReportView({ session }: { session: ResearchSession | null }) {
  const [copied, setCopied] = useState(false);
  const report = session?.report ?? null;

  const copy = async () => {
    if (!report) return;
    try {
      await navigator.clipboard.writeText(report);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      /* Clipboard access can be blocked; download still works. */
    }
  };

  const download = () => {
    if (!report || !session) return;
    const blob = new Blob([report], { type: "text/markdown;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `research-report-${slug(session.topic)}.md`;
    link.click();
    URL.revokeObjectURL(url);
  };

  let body;
  if (!session) {
    body = (
      <div className="state">
        <FileText size={18} />
        <p>No report yet. Start a research session to generate one.</p>
      </div>
    );
  } else if (session.status === "failed") {
    body = (
      <div className="state state-error" role="alert">
        <AlertTriangle size={18} />
        <div>
          <p className="state-title">{session.error?.message ?? "Research failed."}</p>
          {session.error?.reset_at ? (
            <p className="state-detail">Quota resets {formatReset(session.error.reset_at)}.</p>
          ) : null}
          <p className="state-detail">Completed activity remains in the log. You can start a new session.</p>
          {session.error?.detail ? (
            <details className="details">
              <summary>Details</summary>
              <pre className="details-body">{session.error.detail}</pre>
            </details>
          ) : null}
        </div>
      </div>
    );
  } else if (!report) {
    body = (
      <div className="state">
        <Loader2 size={18} className="spin" />
        <p>
          The crew is researching. The report appears here when execution finishes, which can take several minutes
          with a free model.
        </p>
      </div>
    );
  } else {
    // No rehype-raw: embedded HTML in the report is shown as text, not rendered.
    body = (
      <article className="markdown">
        <ReactMarkdown
          remarkPlugins={[remarkGfm]}
          components={{
            a: ({ node: _node, ...props }) => <a {...props} target="_blank" rel="noopener noreferrer" />,
          }}
        >
          {report}
        </ReactMarkdown>
      </article>
    );
  }

  return (
    <section className="panel">
      <div className="panel-head">
        <h2 className="section-title">Research report</h2>
        {report ? (
          <div className="actions">
            <button type="button" className="button" onClick={copy}>
              {copied ? <Check size={14} /> : <Copy size={14} />}
              {copied ? "Copied" : "Copy"}
            </button>
            <button type="button" className="button" onClick={download}>
              <Download size={14} />
              Download .md
            </button>
          </div>
        ) : null}
      </div>
      {session ? <p className="topic">{session.topic}</p> : null}
      {body}
    </section>
  );
}
