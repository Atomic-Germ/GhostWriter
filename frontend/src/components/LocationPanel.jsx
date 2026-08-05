import { useState } from "react";

const EMPTY = {
  name: "",
  type: "",
  description: "",
  notes: "",
};

const FIELDS = [
  ["type", "Type"],
  ["description", "Description"],
  ["notes", "Notes"],
];

export default function LocationPanel({ locations, onCreate, onUpdate, onDelete }) {
  const [selectedId, setSelectedId] = useState(null);
  const [draft, setDraft] = useState(EMPTY);
  const [creating, setCreating] = useState(false);
  const [busy, setBusy] = useState(false);

  const selected = locations.find((l) => l.id === selectedId) || null;

  function openNew() {
    setCreating(true);
    setSelectedId(null);
    setDraft(EMPTY);
  }

  function openExisting(loc) {
    setCreating(false);
    setSelectedId(loc.id);
    setDraft({
      name: loc.name || "",
      type: loc.type || "",
      description: loc.description || "",
      notes: loc.notes || "",
    });
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
        <span className="panel-title">Locations</span>
        <button type="button" className="btn-ghost px-2 py-1 text-xs" onClick={openNew}>
          + New
        </button>
      </div>

      <div className="flex min-h-0 flex-1">
        <ul className="w-36 shrink-0 overflow-y-auto border-r border-panel-border p-2">
          {locations.length === 0 && (
            <li className="px-1 py-4 text-center text-[11px] text-ink-500">
              No locations yet
            </li>
          )}
          {locations.map((l) => (
            <li key={l.id}>
              <button
                type="button"
                onClick={() => openExisting(l)}
                className={`mb-0.5 w-full truncate rounded-md px-2 py-1.5 text-left text-xs ${
                  selectedId === l.id && !creating
                    ? "bg-accent/15 text-accent-glow"
                    : "text-ink-300 hover:bg-panel-raised"
                }`}
              >
                {l.name}
              </button>
            </li>
          ))}
        </ul>

        <div className="min-w-0 flex-1 overflow-y-auto p-3">
          {!creating && !selected ? (
            <p className="py-8 text-center text-xs text-ink-500">
              Select a location or add one.
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
                    rows={key === "notes" ? 3 : 2}
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
