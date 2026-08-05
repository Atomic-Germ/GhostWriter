import { useEffect, useRef, useState } from "react";
import { api } from "../api";
import { useDebouncedCallback } from "../hooks/useDebouncedCallback";
import CharacterPanel from "./CharacterPanel";
import LocationPanel from "./LocationPanel";

function newId() {
  return (
    "srv-" +
    Date.now().toString(36) +
    "-" +
    Math.random().toString(36).slice(2, 10)
  );
}

export default function SeriesPanel({
  seriesName,
  projectId,
  chapters = [],
  activeChapterId = null,
  onOpenProject,
}) {
  const [bible, setBible] = useState(null);
  const [books, setBooks] = useState([]);
  const [loadState, setLoadState] = useState("loading");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  const [extracting, setExtracting] = useState(false);
  const [extractResult, setExtractResult] = useState(null);
  const [extractChapterId, setExtractChapterId] = useState(activeChapterId || "");

  const [canonRunning, setCanonRunning] = useState(false);
  const [canonText, setCanonText] = useState("");
  const canonAbort = useRef(null);

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
          locations: b?.locations || [],
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
        locations: next.locations,
      });
      setBible({
        world_notes: saved.world_notes,
        characters: saved.characters,
        locations: saved.locations,
      });
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

  function patchLocations(locations) {
    const next = { ...bible, locations };
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

  async function handleCreateLocation(body) {
    const created = { ...body, id: newId() };
    patchLocations([...(bible.locations || []), created]);
    return created;
  }

  async function handleUpdateLocation(id, body) {
    patchLocations(
      (bible.locations || []).map((l) => (l.id === id ? { ...l, ...body } : l))
    );
  }

  async function handleDeleteLocation(id) {
    patchLocations((bible.locations || []).filter((l) => l.id !== id));
  }

  function handleWorldNotes(text) {
    const next = { ...bible, world_notes: text };
    setBible(next);
    saveBible(next);
  }

  async function handleExtract() {
    setExtracting(true);
    setError("");
    setExtractResult(null);
    try {
      const result = await api.extractFromStory(projectId, {
        project_id: projectId,
        chapter_id: extractChapterId || undefined,
      });
      // Normalize facts (strings) into selectable objects; default all selected
      setExtractResult({
        characters: (result.characters || []).map((c) => ({ ...c, selected: true })),
        locations: (result.locations || []).map((l) => ({ ...l, selected: true })),
        world_facts: (result.world_facts || []).map((text) => ({
          text,
          selected: true,
        })),
        raw: result.raw || "",
      });
    } catch (err) {
      setError(err.message || "Extraction failed");
    } finally {
      setExtracting(false);
    }
  }

  function handleMergeExtract() {
    if (!extractResult || !bible) return;
    const selectedChars =
      extractResult.characters?.filter((c) => c.selected) || [];
    const selectedLocs =
      extractResult.locations?.filter((l) => l.selected) || [];
    const selectedFacts =
      extractResult.world_facts?.filter((f) => f.selected).map((f) => f.text) || [];

    const existing = new Set(
      (bible.characters || []).map((c) => c.name.trim().toLowerCase())
    );
    const additions = selectedChars
      .filter((c) => !existing.has((c.name || "").trim().toLowerCase()))
      .map((c) => ({
        name: c.name,
        role: c.role || "",
        physical_traits: c.physical_traits || "",
        personality: c.personality || "",
        motivations: c.motivations || "",
        speech_patterns: c.speech_patterns || "",
        backstory: c.backstory || "",
        relationships: c.relationships || "",
        notes: c.notes || "",
        id: newId(),
      }));

    const existingLocs = new Set(
      (bible.locations || []).map((l) => l.name.trim().toLowerCase())
    );
    const locationAdditions = selectedLocs
      .filter((l) => !existingLocs.has((l.name || "").trim().toLowerCase()))
      .map((l) => ({
        name: l.name,
        type: l.type || "",
        description: l.description || "",
        notes: l.notes || "",
        id: newId(),
      }));

    // Build ONE next bible and save once, so the cast, locations, and world notes
    // persist together (previously a second save used a stale closure and dropped
    // earlier changes).
    const nextCharacters = [...(bible.characters || []), ...additions];
    const nextLocations = [...(bible.locations || []), ...locationAdditions];

    const notesLines = (bible.world_notes || "").split("\n").filter((l) => l.trim());
    for (const fact of selectedFacts) {
      if (!notesLines.some((l) => l.toLowerCase().includes(fact.toLowerCase()))) {
        notesLines.push(`- ${fact}`);
      }
    }
    const nextWorldNotes = notesLines.join("\n");

    if (additions.length || locationAdditions.length || selectedFacts.length) {
      const next = {
        characters: nextCharacters,
        locations: nextLocations,
        world_notes: nextWorldNotes,
      };
      setBible(next);
      saveBible(next);
    }
    setExtractResult(null);
    setError("");
  }

  function toggleCharSelected(name) {
    setExtractResult((prev) => ({
      ...prev,
      characters: prev.characters.map((c) =>
        c.name === name ? { ...c, selected: !c.selected } : c
      ),
    }));
  }

  function toggleFactSelected(factText) {
    setExtractResult((prev) => ({
      ...prev,
      world_facts: prev.world_facts.map((f) =>
        f.text === factText ? { ...f, selected: !f.selected } : f
      ),
    }));
  }

  function toggleLocationSelected(name) {
    setExtractResult((prev) => ({
      ...prev,
      locations: prev.locations.map((l) =>
        l.name === name ? { ...l, selected: !l.selected } : l
      ),
    }));
  }

  async function handleCanonCheck() {
    const controller = new AbortController();
    canonAbort.current = controller;
    setCanonRunning(true);
    setCanonText("");
    setError("");
    try {
      await api.assistStream(
        {
          project_id: projectId,
          mode: "canon",
          prompt:
            "Does this manuscript fit the established canon? Flag world-rule/geography/history " +
            "contradictions, renamed things already in the bible, and relationship clashes. " +
            "End with a clear line: CONSISTENT, or a list of conflicts + what would be new canon.",
        },
        {
          signal: controller.signal,
          onMeta: (meta) => {
            if (meta?.llm_available === false) {
              setCanonText(
                "**No LLM connected.** Connect a local model to compare this book against " +
                  "the universe's canon."
              );
              controller.abort();
            }
          },
          onToken: (token, full) => setCanonText(full),
          onDone: () => setCanonRunning(false),
          onError: (err) => {
            setError(err.message || "Canon check failed");
            setCanonRunning(false);
          },
        }
      );
    } catch (err) {
      if (err.name !== "AbortError") {
        setError(err.message || "Canon check failed");
      }
      setCanonRunning(false);
    } finally {
      if (canonAbort.current === controller) canonAbort.current = null;
    }
  }

  function handleStopCanon() {
    canonAbort.current?.abort();
    setCanonRunning(false);
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
          Shared worldbuilding, cast + locations for every book in this series. The
          AI consults this (plus each book's own notes) in every tool.
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

      <div className="flex flex-wrap items-center gap-1.5 border-b border-panel-border px-3 py-2">
        <span className="text-[10px] font-semibold uppercase tracking-wider text-ink-500">
          Extract from
        </span>
        <select
          value={extractChapterId}
          onChange={(e) => setExtractChapterId(e.target.value)}
          className="cursor-pointer rounded border border-panel-border bg-panel/60 px-1.5 py-1 text-[11px] text-ink-300 hover:bg-panel-raised focus:outline-none"
          title="Read the whole book, or focus on one chapter to find the characters it introduces"
        >
          <option value="">Whole book</option>
          {chapters.map((c) => (
            <option key={c.id} value={c.id}>
              {c.title || "Untitled chapter"}
            </option>
          ))}
        </select>
        <button
          type="button"
          className="btn-ghost px-2 py-1 text-xs"
          onClick={handleExtract}
          disabled={extracting}
          title={
            extractChapterId
              ? "Ask the model to read this chapter and propose the characters, locations + world facts it introduces (nothing is written for you — review before adding)"
              : "Ask the model to read this book and propose new characters, locations + world facts (nothing is written for you — review before adding)"
          }
        >
          {extracting ? "Reading…" : "Extract from story"}
        </button>
        <button
          type="button"
          className="btn-ghost px-2 py-1 text-xs"
          onClick={canonRunning ? handleStopCanon : handleCanonCheck}
          title="Compare this manuscript against the series bible + every other book's cast/world to catch canon conflicts before committing it"
        >
          {canonRunning ? "Stop" : "Canon check"}
        </button>
      </div>

      {error && (
        <div className="border-b border-red-900/40 bg-red-950/30 px-3 py-1.5 text-xs text-red-200">
          {error}
          <button type="button" className="ml-2 underline" onClick={() => setError("")}>
            dismiss
          </button>
        </div>
      )}

      {canonRunning && (
        <div className="flex items-center gap-2 border-b border-panel-border px-3 py-2">
          <span className="text-xs text-ink-300">Checking this book against canon…</span>
          <button
            type="button"
            className="underline text-[11px] text-ink-500 hover:text-red-300"
            onClick={handleStopCanon}
          >
            stop
          </button>
        </div>
      )}

      {canonText && !extractResult && (
        <div className="min-h-0 flex-1 overflow-y-auto border-b border-panel-border bg-ink-950/40 p-3">
          <div className="mb-2 flex items-center justify-between">
            <span className="panel-title">Canon review</span>
            <div className="flex gap-1.5">
              {canonRunning && (
                <button
                  type="button"
                  className="btn-ghost px-2 py-1 text-xs"
                  onClick={handleStopCanon}
                >
                  Stop
                </button>
              )}
              <button
                type="button"
                className="btn-ghost px-2 py-1 text-xs"
                onClick={() => { setCanonText(""); setExtractResult(null); }}
              >
                Dismiss
              </button>
            </div>
          </div>
          <p className="mb-2 text-[11px] text-ink-500">
            This checks the manuscript against the series bible and every other book's
            cast and world notes. Imperfect — verify anything it flags before acting.
          </p>
          <pre className="whitespace-pre-wrap text-xs leading-relaxed text-ink-200">
            {canonText}
          </pre>
        </div>
      )}

      {extractResult && (
        <div className="flex min-h-0 flex-1 flex-col border-b border-panel-border bg-ink-950/40">
          <div className="flex items-center justify-between border-b border-panel-border px-3 py-2">
            <span className="panel-title">Extracted from this book</span>
            <div className="flex gap-1.5">
              <button
                type="button"
                className="btn-ghost px-2 py-1 text-xs"
                onClick={() => setExtractResult(null)}
              >
                Dismiss
              </button>
              <button
                type="button"
                className="btn-primary px-2 py-1 text-xs"
                onClick={handleMergeExtract}
              >
                Add selected
              </button>
            </div>
          </div>
          <div className="min-h-0 flex-1 overflow-y-auto p-3">
            <p className="mb-2 text-[11px] text-ink-500">
              Imperfect by design — review and untick anything that's wrong before
              adding. Nothing is written for you; this only lowers the overhead of
              transcribing what the story already established.
            </p>

            {extractResult.characters?.length > 0 && (
              <div className="mb-4">
                <div className="mb-1 text-[10px] font-semibold uppercase tracking-wider text-ink-500">
                  Characters
                </div>
                <ul className="space-y-1.5">
                  {extractResult.characters.map((c) => (
                    <li key={c.name}>
                      <label className="flex cursor-pointer items-start gap-2 rounded-lg border border-panel-border bg-panel/40 px-2.5 py-2">
                        <input
                          type="checkbox"
                          className="mt-0.5"
                          checked={!!c.selected}
                          onChange={() => toggleCharSelected(c.name)}
                        />
                        <span className="min-w-0">
                          <span className="block text-xs font-medium text-ink-200">
                            {c.name}
                            {c.role ? (
                              <span className="ml-1.5 text-ink-500">· {c.role}</span>
                            ) : null}
                          </span>
                          {(c.physical_traits ||
                            c.personality ||
                            c.relationships ||
                            c.backstory) && (
                            <span className="mt-0.5 block text-[11px] leading-snug text-ink-400">
                              {[c.physical_traits, c.personality, c.relationships, c.backstory]
                                .filter(Boolean)
                                .join(" · ")}
                            </span>
                          )}
                        </span>
                      </label>
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {extractResult.locations?.length > 0 && (
              <div className="mb-4">
                <div className="mb-1 text-[10px] font-semibold uppercase tracking-wider text-ink-500">
                  Locations
                </div>
                <ul className="space-y-1.5">
                  {extractResult.locations.map((l) => (
                    <li key={l.name}>
                      <label className="flex cursor-pointer items-start gap-2 rounded-lg border border-panel-border bg-panel/40 px-2.5 py-2">
                        <input
                          type="checkbox"
                          className="mt-0.5"
                          checked={!!l.selected}
                          onChange={() => toggleLocationSelected(l.name)}
                        />
                        <span className="min-w-0">
                          <span className="block text-xs font-medium text-ink-200">
                            {l.name}
                            {l.type ? (
                              <span className="ml-1.5 text-ink-500">· {l.type}</span>
                            ) : null}
                          </span>
                          {l.description && (
                            <span className="mt-0.5 block text-[11px] leading-snug text-ink-400">
                              {l.description}
                            </span>
                          )}
                        </span>
                      </label>
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {extractResult.world_facts?.length > 0 && (
              <div>
                <div className="mb-1 text-[10px] font-semibold uppercase tracking-wider text-ink-500">
                  World facts
                </div>
                <ul className="space-y-1.5">
                  {extractResult.world_facts.map((f) => (
                    <li key={f.text}>
                      <label className="flex cursor-pointer items-start gap-2 rounded-lg border border-panel-border bg-panel/40 px-2.5 py-2">
                        <input
                          type="checkbox"
                          className="mt-0.5"
                          checked={!!f.selected}
                          onChange={() => toggleFactSelected(f.text)}
                        />
                        <span className="text-[11px] leading-snug text-ink-300">
                          {f.text}
                        </span>
                      </label>
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {!extractResult.characters?.length &&
              !extractResult.locations?.length &&
              !extractResult.world_facts?.length && (
              <div className="py-6 text-center">
                <p className="text-xs text-ink-500">
                  Nothing parsed. {extractResult.raw ? "Model returned:" : ""}
                </p>
                {extractResult.raw && (
                  <p className="mt-2 px-4 text-[11px] leading-snug text-ink-600">
                    Thinking models sometimes spend their whole output budget on a
                    reasoning preamble and never write the JSON. Retry — the app will
                    give the model a strict second chance automatically.
                  </p>
                )}
              </div>
            )}
            {extractResult.raw && (
              <details className="mt-3 rounded-lg border border-panel-border bg-ink-950/50 p-2">
                <summary className="cursor-pointer text-[10px] uppercase tracking-wide text-ink-500">
                  Raw model output
                </summary>
                <pre className="mt-2 max-h-48 overflow-y-auto whitespace-pre-wrap font-mono text-[10px] leading-relaxed text-ink-400">
                  {extractResult.raw}
                </pre>
              </details>
            )}
          </div>
        </div>
      )}

      {!extractResult && (
        <div className="flex min-h-0 flex-1 flex-col overflow-y-auto">
          <div className="flex min-h-[140px] flex-[3] flex-col border-b border-panel-border">
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

          <div className="min-h-[160px] flex-[4] border-b border-panel-border">
            <CharacterPanel
              characters={bible.characters || []}
              onCreate={handleCreateCharacter}
              onUpdate={handleUpdateCharacter}
              onDelete={handleDeleteCharacter}
            />
          </div>

          <div className="min-h-[160px] flex-[3]">
            <LocationPanel
              locations={bible.locations || []}
              onCreate={handleCreateLocation}
              onUpdate={handleUpdateLocation}
              onDelete={handleDeleteLocation}
            />
          </div>
        </div>
      )}
    </div>
  );
}
