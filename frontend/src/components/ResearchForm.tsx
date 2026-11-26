import { useState, type FormEvent, type KeyboardEvent } from "react";
import { Loader2, Play } from "lucide-react";

interface Props {
  busy: boolean;
  disabled: boolean;
  error: string | null;
  onSubmit: (topic: string) => void;
}

const EXAMPLE = "Compare LangChain Deep Agents and CrewAI.";

export function ResearchForm({ busy, disabled, error, onSubmit }: Props) {
  const [topic, setTopic] = useState("");
  const [touched, setTouched] = useState(false);
  const empty = topic.trim().length === 0;

  const submit = (event?: FormEvent) => {
    event?.preventDefault();
    setTouched(true);
    if (empty || busy || disabled) return;
    onSubmit(topic.trim());
  };

  const onKeyDown = (event: KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === "Enter" && (event.metaKey || event.ctrlKey)) submit();
  };

  const validation = touched && empty ? "Enter a research topic or question." : null;
  const message = validation ?? error;

  return (
    <section className="panel">
      <div className="panel-head">
        <h1 className="title">Research Workspace</h1>
      </div>
      <form className="form" onSubmit={submit} noValidate>
        <label htmlFor="topic" className="label">
          Research topic or question
        </label>
        <textarea
          id="topic"
          className="textarea"
          rows={4}
          maxLength={2000}
          placeholder={EXAMPLE}
          value={topic}
          disabled={busy}
          onChange={(e) => setTopic(e.target.value)}
          onKeyDown={onKeyDown}
          aria-invalid={Boolean(validation)}
          aria-describedby="topic-help"
        />
        <div className="form-row">
          {message ? (
            <p id="topic-help" className="hint hint-error" role="alert">
              {message}
            </p>
          ) : (
            <p id="topic-help" className="hint">
              Example:{" "}
              <button type="button" className="link-button" onClick={() => setTopic(EXAMPLE)} disabled={busy}>
                {EXAMPLE}
              </button>
            </p>
          )}
          <button type="submit" className="button button-primary" disabled={busy || disabled}>
            {busy ? <Loader2 size={15} className="spin" /> : <Play size={15} />}
            {busy ? "Researching…" : "Start Research"}
          </button>
        </div>
      </form>
    </section>
  );
}
