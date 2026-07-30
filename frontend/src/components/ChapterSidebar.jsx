export default function ChapterSidebar({
  project,
  chapters,
  activeChapterId,
  onSelect,
  onAdd,
  onDelete,
  onBack,
}) {
  const totalWords = chapters.reduce((n, c) => n + (c.word_count || 0), 0);

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

      <ul className="flex-1 overflow-y-auto px-2 pb-4">
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
    </aside>
  );
}
