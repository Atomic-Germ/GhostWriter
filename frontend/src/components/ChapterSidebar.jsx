import { useState } from "react";

const EXPORTS = [
  { id: "markdown", label: "Markdown (.md)" },
  { id: "docx", label: "Word (.docx)" },
  { id: "epub", label: "EPUB ebook" },
  { id: "html", label: "HTML (print)" },
  { id: "txt", label: "Plain text" },
  { id: "json", label: "Full backup (.json)" },
];

export default function ChapterSidebar({
  project,
  chapters,
  activeChapterId,
  onSelect,
  onAdd,
  onDelete,
  onBack,
  onExport,
}) {
  const totalWords = chapters.reduce((n, c) => n + (c.word_count || 0), 0);
  const [exportOpen, setExportOpen] = useState(false);
  const [exporting, setExporting] = useState(null);

  async function handleExport(fmt) {
    if (!onExport || exporting) return;
    setExporting(fmt);
    try {
      await onExport(fmt);
      setExportOpen(false);
    } finally {
      setExporting(null);
    }
  }

  return (
    <aside className="flex h-full w-60 shrink-0 flex-col border-r border-panel-border bg-panel/60">
      <div className="border-b border-panel-border px-3 py-3">
        <button type="button" className="btn-ghost mb-2 -ml-1 px-2 py-1 text-xs" onClick={onBack}>
          ← Projects
        </button>
        <h2 className="truncate font-serif text-base text-ink-50" title={project?.title}>
          {project?.title}
        </h2>
        <p className="mt-1 font-mono text-[11px] text-ink-500">
          {totalWords.toLocaleString()} words · {chapters.length} ch.
        </p>
      </div>

      <div className="flex items-center justify-between px-3 py-2">
        <span className="panel-title">Chapters</span>
        <button type="button" className="btn-ghost px-2 py-1 text-xs" onClick={onAdd}>
          + Add
        </button>
      </div>

      <ul className="min-h-0 flex-1 overflow-y-auto px-2 pb-2">
        {chapters.length === 0 && (
          <li className="px-2 py-6 text-center text-xs text-ink-500">
            No chapters yet. Add one to begin.
          </li>
        )}
        {chapters.map((ch, i) => {
          const active = ch.id === activeChapterId;
          return (
            <li key={ch.id} className="group mb-0.5 flex items-stretch">
              <button
                type="button"
                onClick={() => onSelect(ch.id)}
                className={`flex min-w-0 flex-1 flex-col rounded-lg px-2.5 py-2 text-left transition ${
                  active
                    ? "bg-accent/15 text-accent-glow"
                    : "text-ink-300 hover:bg-panel-raised hover:text-ink-100"
                }`}
              >
                <span className="truncate text-sm font-medium">
                  <span className="mr-1.5 font-mono text-[10px] opacity-60">{i + 1}</span>
                  {ch.title}
                </span>
                <span className="font-mono text-[10px] opacity-50">
                  {(ch.word_count || 0).toLocaleString()} w
                </span>
              </button>
              <button
                type="button"
                className="invisible rounded px-1.5 text-ink-600 hover:text-red-300 group-hover:visible"
                title="Delete chapter"
                onClick={() => {
                  if (confirm(`Delete “${ch.title}”?`)) onDelete(ch.id);
                }}
              >
                ×
              </button>
            </li>
          );
        })}
      </ul>

      <div className="relative border-t border-panel-border p-2">
        <button
          type="button"
          className="btn-ghost w-full justify-between border border-panel-border px-2.5 py-2 text-xs"
          onClick={() => setExportOpen((v) => !v)}
          disabled={!project?.id}
        >
          <span>Export</span>
          <span className="font-mono text-[10px] text-ink-500">{exportOpen ? "▴" : "▾"}</span>
        </button>
        {exportOpen && (
          <ul className="mt-1 overflow-hidden rounded-lg border border-panel-border bg-panel-raised shadow-soft">
            {EXPORTS.map((f) => (
              <li key={f.id}>
                <button
                  type="button"
                  className="w-full px-3 py-2 text-left text-xs text-ink-200 transition hover:bg-accent/15 hover:text-accent-glow disabled:opacity-50"
                  disabled={!!exporting}
                  onClick={() => handleExport(f.id)}
                >
                  {exporting === f.id ? "Exporting…" : f.label}
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>
    </aside>
  );
}
