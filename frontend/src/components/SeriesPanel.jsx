import { useEffect, useState } from "react";
import { api } from "../api";
import { useDebouncedCallback } from "../hooks/useDebouncedCallback";
import CharacterPanel from "./CharacterPanel";

function newId() {
  return (
    "srv-" +
    Date.now().toString(36) +
    "-" +
    Math.random().toString(36).slice(2, 10)
  );
}

export default function SeriesPanel({ seriesName, onOpenProject }) {
  const [bible, setBible] = useState(null);
  const [books, setBooks] = useState([]);
  const [loadState, setLoadState] = useState("loading");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;
    (async () => {
      setLoadState("loading");
      setError("");
      try {
        const [b, seriesList] = await Promise.all([
          api.getSeriesBible(seriesName),
          api.listSeries(),
        ]);
        if (cancelled) return;
        setBible({
          world_notes: b?.world_notes || "",
          characters: b?.characters || [],
        });
        const match = seriesList.find((s) => s.name === seriesName);
        setBooks(match?.books || []);
        setLoadState("ready");
      } catch (err) {
        if (cancelled) return;
        setError(err.message);
        setLoadState("error");
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [seriesName]);

  const saveBible = useDebouncedCallback(async (next) => {
    setSaving(true);
    try {
      const saved = await api.updateSeriesBible(seriesName, {
        world_notes: next.world_notes,
        characters: next.characters,
      });
      setBible({ world_notes: saved.world_notes, characters: saved.characters });
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  }, 800);

  function patchCharacters(characters) {
    const next = { ...bible, characters };
    setBible(next);
    saveBible(next);
  }

  async function handleCreateCharacter(body) {
    const created = { ...body, id: newId() };
    patchCharacters([...(bible.characters || []), created]);
    return created;
  }

  async function handleUpdateCharacter(id, body) {
    patchCharacters(
      (bible.characters || []).map((c) => (c.id === id ? { ...c, ...body } : c))
    );
  }

  async function handleDeleteCharacter(id) {
    patchCharacters((bible.characters || []).filter((c) => c.id !== id));
  }

  function handleWorldNotes(text) {
    const next = { ...bible, world_notes: text };
    setBible(next);
    saveBible(next);
  }

  if (loadState === "loading") {
    return (
      <div className="flex h-full items-center justify-center text-sm text-ink-400">
        Loading series…
      </div>
    );
  }

  if (loadState === "error") {
    return (
      <div className="flex h-full items-center justify-center p-6 text-sm text-red-300">
        {error}
      </div>
    );
  }

  return (
    <div className="flex h-full flex-col">
      <div className="border-b border-panel-border px-3 py-2">
        <div className="flex items-center justify-between">
          <span className="panel-title">{seriesName}</span>
          <span className="font-mono text-[10px] text-ink-600">
            {saving ? "Saving…" : "Auto-save"}
          </span>
        </div>
        <p className="mt-1 text-[11px] leading-snug text-ink-500">
          Shared worldbuilding + cast for every book in this series. The AI
          consults this (plus each book's own notes) in every tool.
        </p>
      </div>

      {books.length > 0 && (
        <div className="border-b border-panel-border px-3 py-2">
          <div className="mb-1 text-[10px] font-semibold uppercase tracking-wider text-ink-500">
            Books
          </div>
          <ul className="flex flex-wrap gap-1">
            {books.map((b) => (
              <li key={b.id}>
                <button
                  type="button"
                  onClick={() => onOpenProject?.(b.id)}
                  className="rounded-full border border-panel-border px-2 py-0.5 font-mono text-[11px] text-ink-300 hover:border-accent/40 hover:text-accent"
                  title={b.description || b.title}
                >
                  {b.series_position ? `${b.series_position}. ` : ""}
                  {b.title}
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}

      {error && (
        <div className="border-b border-red-900/40 bg-red-950/30 px-3 py-1.5 text-xs text-red-200">
          {error}
          <button type="button" className="ml-2 underline" onClick={() => setError("")}>
            dismiss
          </button>
        </div>
      )}

      <div className="min-h-0 flex-1 overflow-y-auto">
        <div className="flex h-[38%] min-h-[140px] flex-col border-b border-panel-border">
          <div className="border-b border-panel-border px-3 py-2">
            <span className="text-[10px] font-semibold uppercase tracking-wider text-ink-500">
              Worldbuilding bible
            </span>
          </div>
          <textarea
            className="min-h-0 flex-1 resize-none bg-transparent p-3 text-xs leading-relaxed text-ink-200 placeholder:text-ink-600 focus:outline-none"
            value={bible.world_notes || ""}
            onChange={(e) => handleWorldNotes(e.target.value)}
            placeholder={
              "Canon rules, places, history, factions, magic/tech, " +
              "and anything that must stay consistent across every book…"
            }
          />
        </div>

        <div className="min-h-0 flex-1">
          <CharacterPanel
            characters={bible.characters || []}
            onCreate={handleCreateCharacter}
            onUpdate={handleUpdateCharacter}
            onDelete={handleDeleteCharacter}
          />
        </div>
      </div>
    </div>
  );
}
