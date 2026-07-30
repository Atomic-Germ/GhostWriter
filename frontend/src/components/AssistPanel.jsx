import { useState } from "react";
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
  onAssist,
  onInsert,
  onIndex,
  llmAvailable,
  indexing,
}) {
  const [mode, setMode] = useState("brainstorm");
  const [prompt, setPrompt] = useState("");
  const [response, setResponse] = useState("");
  const [sources, setSources] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [lastLlm, setLastLlm] = useState(null);

  async function handleSubmit(e) {
    e.preventDefault();
    if (!prompt.trim() && mode !== "continue" && mode !== "consistency") return;
    setLoading(true);
    setError("");
    try {
      const defaultPrompts = {
        continue: "Continue the scene from where the draft leaves off.",
        consistency:
          "Analyze the current draft excerpt for contradictions with character profiles and established lore.",
      };
      const result = await onAssist({
        mode,
        prompt: prompt.trim() || defaultPrompts[mode] || "Help with this scene.",
      });
      setResponse(result.response);
      setSources(result.sources || []);
      setLastLlm(result.llm_available);
    } catch (err) {
      setError(err.message || "Assist failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center justify-between border-b border-panel-border px-3 py-2">
        <span className="panel-title">GhostWriter AI</span>
        <div className="flex items-center gap-2">
          <span
            className={`font-mono text-[10px] ${llmAvailable || lastLlm ? "text-emerald-400" : "text-ink-500"}`}
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
        />
        <button type="submit" className="btn-primary w-full" disabled={loading}>
          {loading ? "Thinking…" : "Ask GhostWriter"}
        </button>
      </form>

      <div className="min-h-0 flex-1 overflow-y-auto p-3">
        {error && (
          <p className="mb-3 rounded-lg border border-red-900/50 bg-red-950/40 px-3 py-2 text-xs text-red-200">
            {error}
          </p>
        )}
        {!response && !error && (
          <p className="py-6 text-center text-xs leading-relaxed text-ink-500">
            Grounded in your chapters, character dossiers, and world notes via RAG.
            Connect llama.cpp, Ollama, or any OpenAI-compatible API for full power.
          </p>
        )}
        {response && (
          <>
            <div className="prose-gw mb-3">
              <ReactMarkdown>{response}</ReactMarkdown>
            </div>
            {mode === "continue" && (
              <button
                type="button"
                className="btn-ghost mb-3 w-full border border-panel-border text-xs"
                onClick={() => onInsert(response)}
              >
                Insert into chapter
              </button>
            )}
            {sources.length > 0 && (
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
