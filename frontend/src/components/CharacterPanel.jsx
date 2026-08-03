import { useState } from "react";

const EMPTY = {
  name: "",
  role: "",
  physical_traits: "",
  personality: "",
  motivations: "",
  speech_patterns: "",
  backstory: "",
  relationships: "",
  notes: "",
};

const FIELDS = [
  ["role", "Role"],
  ["physical_traits", "Physical traits"],
  ["personality", "Personality"],
  ["motivations", "Motivations"],
  ["speech_patterns", "Speech patterns"],
  ["backstory", "Backstory"],
  ["relationships", "Relationships"],
  ["notes", "Notes"],
];

export default function CharacterPanel({
  characters,
  onCreate,
  onUpdate,
  onDelete,
  seriesName,
  onImportFromSeries,
}) {
  const [selectedId, setSelectedId] = useState(null);
  const [draft, setDraft] = useState(EMPTY);
  const [creating, setCreating] = useState(false);
  const [busy, setBusy] = useState(false);
  const [importing, setImporting] = useState(false);
  const [importMsg, setImportMsg] = useState("");

  const selected = characters.find((c) => c.id === selectedId) || null;

  function openNew() {
    setCreating(true);
    setSelectedId(null);
    setDraft(EMPTY);
  }

  function openExisting(c) {
    setCreating(false);
    setSelectedId(c.id);
    setDraft({
      name: c.name || "",
      role: c.role || "",
      physical_traits: c.physical_traits || "",
      personality: c.personality || "",
      motivations: c.motivations || "",
      speech_patterns: c.speech_patterns || "",
      backstory: c.backstory || "",
      relationships: c.relationships || "",
      notes: c.notes || "",
    });
  }

  async function handleImportFromSeries() {
    if (!onImportFromSeries) return;
    setImporting(true);
    setImportMsg("");
    try {
      const added = await onImportFromSeries();
      setImportMsg(
        added > 0
          ? `Imported ${added} character${added === 1 ? "" : "s"} from the series bible.`
          : "All series cast already in this book."
      );
    } catch (err) {
      setImportMsg(err?.message || "Import failed");
    } finally {
      setImporting(false);
    }
  }

  async function handleSave(e) {
    e.preventDefault();
    if (!draft.name.trim()) return;
    setBusy(true);
    try {
      if (creating) {
        const created = await onCreate(draft);
        setCreating(false);
        setSelectedId(created.id);
      } else if (selectedId) {
        await onUpdate(selectedId, draft);
      }
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center justify-between border-b border-panel-border px-3 py-2">
        <span className="panel-title">Characters</span>
        <div className="flex items-center gap-2">
          {onImportFromSeries && (
            <button
              type="button"
              className="btn-ghost px-2 py-1 text-xs"
              onClick={handleImportFromSeries}
              disabled={importing}
              title={`Pull the series cast (${seriesName || "series bible"}) into this book so Arthur can reference them`}
            >
              {importing ? "Importing…" : "Import from series"}
            </button>
          )}
          <button type="button" className="btn-ghost px-2 py-1 text-xs" onClick={openNew}>
            + New
          </button>
        </div>
      </div>
      {importMsg && (
        <div
          className={`border-b border-panel-border px-3 py-1.5 text-xs ${
            importMsg.startsWith("Imported") ? "text-accent" : "text-red-300"
          }`}
        >
          {importMsg}
        </div>
      )}

      <div className="flex min-h-0 flex-1">
        <ul className="w-36 shrink-0 overflow-y-auto border-r border-panel-border p-2">
          {characters.length === 0 && (
            <li className="px-1 py-4 text-center text-[11px] text-ink-500">No cast yet</li>
          )}
          {characters.map((c) => (
            <li key={c.id}>
              <button
                type="button"
                onClick={() => openExisting(c)}
                className={`mb-0.5 w-full truncate rounded-md px-2 py-1.5 text-left text-xs ${
                  selectedId === c.id && !creating
                    ? "bg-accent/15 text-accent-glow"
                    : "text-ink-300 hover:bg-panel-raised"
                }`}
              >
                {c.name}
              </button>
            </li>
          ))}
        </ul>

        <div className="min-w-0 flex-1 overflow-y-auto p-3">
          {!creating && !selected ? (
            <p className="py-8 text-center text-xs text-ink-500">
              Select a character or create a dossier.
            </p>
          ) : (
            <form onSubmit={handleSave} className="space-y-3">
              <div>
                <label className="label">Name</label>
                <input
                  className="input"
                  value={draft.name}
                  onChange={(e) => setDraft({ ...draft, name: e.target.value })}
                  required
                />
              </div>
              {FIELDS.map(([key, label]) => (
                <div key={key}>
                  <label className="label">{label}</label>
                  <textarea
                    className="input min-h-[56px] resize-y text-xs"
                    value={draft[key]}
                    onChange={(e) => setDraft({ ...draft, [key]: e.target.value })}
                    rows={key === "backstory" || key === "notes" ? 3 : 2}
                  />
                </div>
              ))}
              <div className="flex gap-2 pt-1">
                <button type="submit" className="btn-primary flex-1" disabled={busy}>
                  {busy ? "Saving…" : creating ? "Create" : "Save"}
                </button>
                {!creating && selectedId && (
                  <button
                    type="button"
                    className="btn-danger"
                    onClick={async () => {
                      if (!confirm(`Delete ${draft.name}?`)) return;
                      await onDelete(selectedId);
                      setSelectedId(null);
                      setDraft(EMPTY);
                    }}
                  >
                    Delete
                  </button>
                )}
              </div>
            </form>
          )}
        </div>
      </div>
    </div>
  );
}
