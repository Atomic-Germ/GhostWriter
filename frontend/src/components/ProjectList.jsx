import { useState } from "react";

export default function ProjectList({
  projects,
  loading,
  onOpen,
  onCreate,
  onDelete,
}) {
  const [form, setForm] = useState({
    title: "",
    genre: "",
    description: "",
    premise: "",
  });
  const [showForm, setShowForm] = useState(false);
  const [creating, setCreating] = useState(false);

  async function handleCreate(e) {
    e.preventDefault();
    if (!form.title.trim()) return;
    setCreating(true);
    try {
      await onCreate(form);
      setForm({ title: "", genre: "", description: "", premise: "" });
      setShowForm(false);
    } finally {
      setCreating(false);
    }
  }

  return (
    <div className="mx-auto flex min-h-full max-w-4xl flex-col px-6 py-12">
      <header className="mb-10">
        <div className="mb-2 flex items-center gap-3">
          <div className="flex h-10 w-10 items-center justify-center rounded-xl border border-accent/30 bg-accent/10 font-serif text-lg text-accent">
            G
          </div>
          <div>
            <h1 className="font-serif text-3xl font-semibold tracking-tight text-ink-50">
              GhostWriter
            </h1>
            <p className="text-sm text-ink-400">Story-aware writing companion</p>
          </div>
        </div>
      </header>

      <div className="mb-6 flex items-center justify-between">
        <h2 className="panel-title">Your manuscripts</h2>
        <button
          type="button"
          className="btn-primary"
          onClick={() => setShowForm((v) => !v)}
        >
          {showForm ? "Cancel" : "New project"}
        </button>
      </div>

      {showForm && (
        <form onSubmit={handleCreate} className="card mb-8 grid gap-4 p-5 sm:grid-cols-2">
          <div className="sm:col-span-2">
            <label className="label">Title</label>
            <input
              className="input"
              value={form.title}
              onChange={(e) => setForm({ ...form, title: e.target.value })}
              placeholder="The Last Cartographer"
              autoFocus
              required
            />
          </div>
          <div>
            <label className="label">Genre</label>
            <input
              className="input"
              value={form.genre}
              onChange={(e) => setForm({ ...form, genre: e.target.value })}
              placeholder="Literary fantasy"
            />
          </div>
          <div>
            <label className="label">Premise</label>
            <input
              className="input"
              value={form.premise}
              onChange={(e) => setForm({ ...form, premise: e.target.value })}
              placeholder="One-line hook"
            />
          </div>
          <div className="sm:col-span-2">
            <label className="label">Description</label>
            <textarea
              className="input min-h-[80px] resize-y"
              value={form.description}
              onChange={(e) => setForm({ ...form, description: e.target.value })}
              placeholder="What is this book about?"
            />
          </div>
          <div className="sm:col-span-2 flex justify-end">
            <button type="submit" className="btn-primary" disabled={creating}>
              {creating ? "Creating…" : "Create project"}
            </button>
          </div>
        </form>
      )}

      {loading ? (
        <p className="text-sm text-ink-400">Loading projects…</p>
      ) : projects.length === 0 ? (
        <div className="card flex flex-col items-center gap-3 px-8 py-16 text-center">
          <p className="font-serif text-xl text-ink-200">No manuscripts yet</p>
          <p className="max-w-sm text-sm text-ink-500">
            Create a project to start writing with character dossiers, chapter
            memory, and AI assistance grounded in your story.
          </p>
          <button type="button" className="btn-primary mt-2" onClick={() => setShowForm(true)}>
            Start writing
          </button>
        </div>
      ) : (
        <ul className="grid gap-3">
          {projects.map((p) => (
            <li key={p.id}>
              <div className="card group flex items-stretch overflow-hidden transition hover:border-accent/30">
                <button
                  type="button"
                  onClick={() => onOpen(p.id)}
                  className="flex flex-1 flex-col items-start gap-1 px-5 py-4 text-left"
                >
                  <span className="font-serif text-lg text-ink-50 group-hover:text-accent-glow">
                    {p.title}
                  </span>
                  <span className="line-clamp-2 text-sm text-ink-400">
                    {p.description || p.premise || "No description"}
                  </span>
                  <span className="mt-2 flex flex-wrap gap-3 font-mono text-[11px] text-ink-500">
                    {p.genre && <span>{p.genre}</span>}
                    <span>{p.chapter_count} chapters</span>
                    <span>{p.character_count} characters</span>
                    <span>{p.word_count.toLocaleString()} words</span>
                  </span>
                </button>
                <button
                  type="button"
                  className="btn-ghost border-l border-panel-border px-4 text-ink-500 hover:text-red-300"
                  title="Delete project"
                  onClick={(e) => {
                    e.stopPropagation();
                    if (confirm(`Delete “${p.title}”? This cannot be undone.`)) {
                      onDelete(p.id);
                    }
                  }}
                >
                  Delete
                </button>
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
