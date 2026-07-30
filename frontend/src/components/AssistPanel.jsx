import { useEffect, useRef, useState } from "react";
import ReactMarkdown from "react-markdown";

const MODES = [
  { id: "brainstorm", label: "Brainstorm" },
  { id: "continue", label: "Continue" },
  { id: "consistency", label: "Consistency" },
  { id: "lore", label: "Lore" },
  { id: "plot", label: "Plot" },
];

const PLACEHOLDERS = {
  brainstorm: "Suggest a twist that raises stakes for the protagonist…",
  continue: "Continue from the cursor in the same voice…",
  consistency: "Check this scene against character profiles…",
  lore: "What do we know about the capital's magic laws?",
  plot: "Are there unresolved threads from chapter 1?",
};

export default function AssistPanel({
  onAssistStream,
  onInsert,
  onIndex,
  llmAvailable,
  indexing,
}) {
  const [mode, setMode] = useState("brainstorm");
  const [prompt, setPrompt] = useState("");
  const [response, setResponse] = useState("");
  const [thinking, setThinking] = useState("");
  const [showThinking, setShowThinking] = useState(true);
  const [sources, setSources] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [lastLlm, setLastLlm] = useState(null);
  const [modelName, setModelName] = useState("");
  const abortRef = useRef(null);
  const bottomRef = useRef(null);

  useEffect(() => {
    if (loading && bottomRef.current) {
      bottomRef.current.scrollIntoView({ behavior: "smooth", block: "end" });
    }
  }, [response, thinking, loading]);

  useEffect(() => () => abortRef.current?.abort(), []);

  async function handleSubmit(e) {
    e.preventDefault();
    if (!prompt.trim() && mode !== "continue" && mode !== "consistency") return;

    abortRef.current?.abort();
    const controller = new AbortController();
    abortRef.current = controller;

    setLoading(true);
    setError("");
    setResponse("");
    setThinking("");
    setShowThinking(true);
    setSources([]);
    setModelName("");

    const defaultPrompts = {
      continue: "Continue the scene from where the draft leaves off.",
      consistency:
        "Analyze the current draft excerpt for contradictions with character profiles and established lore.",
    };

    try {
      await onAssistStream(
        {
          mode,
          prompt: prompt.trim() || defaultPrompts[mode] || "Help with this scene.",
        },
        {
          signal: controller.signal,
          onMeta: (meta) => {
            setSources(meta.sources || []);
            setLastLlm(!!meta.llm_available);
            if (meta.model) setModelName(meta.model);
          },
          onToken: (_piece, full) => setResponse(full),
          onThinking: (_piece, full) => setThinking(full),
          onPromoteThinking: (fullThinking) => {
            // reasoning-only models: answer lives in the thinking stream
            setResponse(fullThinking || "");
            setShowThinking(false);
          },
          onDone: (full, meta) => {
            if (full) setResponse(full);
            else if (meta?.thinking) {
              setResponse(meta.thinking);
              setShowThinking(false);
            }
          },
          onError: (msg) => {
            if (!controller.signal.aborted) setError(msg);
          },
        }
      );
    } catch (err) {
      const aborted =
        controller.signal.aborted ||
        err?.name === "AbortError" ||
        err?.message?.includes("aborted");
      if (!aborted) setError(err.message || "Assist failed");
    } finally {
      setLoading(false);
    }
  }

  function handleStop(e) {
    e?.preventDefault?.();
    e?.stopPropagation?.();
    abortRef.current?.abort();
  }

  const displayText = response || (loading && thinking ? "" : thinking);
  const insertable = response || thinking;

  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center justify-between border-b border-panel-border px-3 py-2">
        <span className="panel-title">GhostWriter AI</span>
        <div className="flex items-center gap-2">
          <span
            className={`font-mono text-[10px] ${llmAvailable || lastLlm ? "text-emerald-400" : "text-ink-500"}`}
            title={modelName || undefined}
          >
            {llmAvailable || lastLlm ? "LLM" : "Offline"}
          </span>
          <button
            type="button"
            className="btn-ghost px-2 py-1 text-[11px]"
            onClick={onIndex}
            disabled={indexing}
            title="Re-index story memory"
          >
            {indexing ? "Indexing…" : "Re-index"}
          </button>
        </div>
      </div>

      <div className="flex flex-wrap gap-1 border-b border-panel-border px-2 py-2">
        {MODES.map((m) => (
          <button
            key={m.id}
            type="button"
            onClick={() => setMode(m.id)}
            className={`rounded-md px-2 py-1 text-[11px] transition ${
              mode === m.id
                ? "bg-accent/20 text-accent-glow"
                : "text-ink-400 hover:bg-panel-raised hover:text-ink-200"
            }`}
          >
            {m.label}
          </button>
        ))}
      </div>

      <form onSubmit={handleSubmit} className="border-b border-panel-border p-3">
        <textarea
          className="input mb-2 min-h-[72px] resize-y text-xs"
          value={prompt}
          onChange={(e) => setPrompt(e.target.value)}
          placeholder={PLACEHOLDERS[mode]}
          disabled={loading}
        />
        <button
          type="submit"
          className={`btn-primary w-full ${loading ? "hidden" : ""}`}
          disabled={loading}
          tabIndex={loading ? -1 : 0}
        >
          Ask GhostWriter
        </button>
        <button
          type="button"
          className={`btn-danger w-full ${loading ? "" : "hidden"}`}
          onClick={handleStop}
          onMouseDown={(e) => e.preventDefault()}
          tabIndex={loading ? 0 : -1}
        >
          Stop generating
        </button>
      </form>

      <div className="min-h-0 flex-1 overflow-y-auto p-3">
        {error && (
          <p className="mb-3 rounded-lg border border-red-900/50 bg-red-950/40 px-3 py-2 text-xs text-red-200">
            {error}
          </p>
        )}
        {!displayText && !thinking && !error && !loading && (
          <p className="py-6 text-center text-xs leading-relaxed text-ink-500">
            Grounded in your chapters, character dossiers, and world notes.
            Responses stream token-by-token from your local model.
          </p>
        )}
        {loading && !thinking && !response && (
          <p className="mb-3 font-mono text-[11px] text-accent animate-pulse">
            Generating{modelName ? ` · ${modelName}` : "…"}
          </p>
        )}

        {thinking && showThinking && (
          <details
            className="mb-3 rounded-lg border border-panel-border bg-ink-950/50 open:pb-2"
            open={loading && !response}
          >
            <summary className="cursor-pointer select-none px-2.5 py-1.5 font-mono text-[10px] uppercase tracking-wide text-ink-500">
              {loading && !response ? "Thinking…" : "Model reasoning"}
              <span className="ml-2 normal-case tracking-normal text-ink-600">
                ({thinking.length.toLocaleString()} chars)
              </span>
            </summary>
            <pre className="max-h-40 overflow-y-auto whitespace-pre-wrap px-2.5 pb-1 font-mono text-[10px] leading-relaxed text-ink-400">
              {thinking}
              {loading && !response && (
                <span className="ml-0.5 inline-block h-2.5 w-1 animate-pulse bg-accent align-middle" />
              )}
            </pre>
          </details>
        )}

        {displayText && (
          <>
            <div className="prose-gw mb-3">
              <ReactMarkdown>{displayText}</ReactMarkdown>
              {loading && response && (
                <span className="ml-0.5 inline-block h-3 w-1.5 animate-pulse bg-accent align-middle" />
              )}
            </div>
            <div ref={bottomRef} />
            {mode === "continue" && !loading && insertable && (
              <button
                type="button"
                className="btn-ghost mb-3 w-full border border-panel-border text-xs"
                onClick={() => onInsert(insertable)}
              >
                Insert into chapter
              </button>
            )}
            {sources.length > 0 && !loading && (
              <div className="mt-2 border-t border-panel-border pt-3">
                <p className="panel-title mb-2">Context used</p>
                <ul className="space-y-1">
                  {sources.map((s) => (
                    <li key={s} className="truncate font-mono text-[10px] text-ink-500">
                      {s}
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
