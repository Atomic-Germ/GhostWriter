import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { api } from "../api";
import { useDebouncedCallback } from "../hooks/useDebouncedCallback";
import AssistPanel from "./AssistPanel";
import ChapterSidebar from "./ChapterSidebar";
import CharacterPanel from "./CharacterPanel";
import Editor from "./Editor";
import StatusPill from "./StatusPill";
import StoryMap from "./StoryMap";
import WorldNotes from "./WorldNotes";

function countWords(text) {
  return text.trim() ? text.trim().split(/\s+/).length : 0;
}

export default function Workspace({ projectId, health, onBack }) {
  const [project, setProject] = useState(null);
  const [chapters, setChapters] = useState([]);
  const [characters, setCharacters] = useState([]);
  const [activeChapterId, setActiveChapterId] = useState(null);
  const [rightTab, setRightTab] = useState("ai");
  const [saving, setSaving] = useState(false);
  const [indexing, setIndexing] = useState(false);
  const [error, setError] = useState("");
  const [loadState, setLoadState] = useState("loading");
  const saveGen = useRef(0);
  const latestContent = useRef({});

  const activeChapter = useMemo(
    () => chapters.find((c) => c.id === activeChapterId) || null,
    [chapters, activeChapterId]
  );

  const load = useCallback(async () => {
    setLoadState("loading");
    setError("");
    try {
      const p = await api.getProject(projectId);
      setProject(p);
      const sorted = [...(p.chapters || [])].sort((a, b) => a.order - b.order);
      setChapters(sorted);
      setCharacters(p.characters || []);
      sorted.forEach((c) => {
        latestContent.current[c.id] = c.content || "";
      });
      setActiveChapterId((prev) => {
        if (prev && sorted.some((c) => c.id === prev)) return prev;
        return sorted[0]?.id || null;
      });
      setLoadState("ready");
    } catch (err) {
      setError(err.message);
      setLoadState("error");
    }
  }, [projectId]);

  useEffect(() => {
    load();
  }, [load]);

  const saveChapter = useDebouncedCallback(async (chapterId, patch) => {
    const gen = ++saveGen.current;
    setSaving(true);
    try {
      const updated = await api.updateChapter(projectId, chapterId, patch);
      // Only merge metadata — never clobber newer local text mid-type
      setChapters((prev) =>
        prev.map((c) => {
          if (c.id !== updated.id) return c;
          const local = latestContent.current[c.id];
          const keepLocal =
            local !== undefined && local !== updated.content && patch.content !== undefined;
          return {
            ...updated,
            content: keepLocal ? local : updated.content,
            word_count: keepLocal ? countWords(local) : updated.word_count,
            title: patch.title !== undefined ? c.title : updated.title,
          };
        })
      );
    } catch (err) {
      setError(err.message);
    } finally {
      if (gen === saveGen.current) setSaving(false);
    }
  }, 500);

  async function handleAddChapter() {
    const n = chapters.length + 1;
    const ch = await api.createChapter(projectId, {
      title: `Chapter ${n}`,
      content: "",
      order: chapters.length,
    });
    latestContent.current[ch.id] = "";
    setChapters((prev) => [...prev, ch]);
    setActiveChapterId(ch.id);
  }

  async function handleDeleteChapter(id) {
    await api.deleteChapter(projectId, id);
    delete latestContent.current[id];
    setChapters((prev) => {
      const next = prev.filter((c) => c.id !== id);
      if (activeChapterId === id) {
        setActiveChapterId(next[0]?.id || null);
      }
      return next;
    });
  }

  async function handleCreateCharacter(body) {
    const c = await api.createCharacter(projectId, body);
    setCharacters((prev) => [...prev, c]);
    return c;
  }

  async function handleUpdateCharacter(id, body) {
    const c = await api.updateCharacter(projectId, id, body);
    setCharacters((prev) => prev.map((x) => (x.id === id ? c : x)));
    return c;
  }

  async function handleDeleteCharacter(id) {
    await api.deleteCharacter(projectId, id);
    setCharacters((prev) => prev.filter((c) => c.id !== id));
  }

  async function handleSaveWorld(notes) {
    const p = await api.updateWorldNotes(projectId, notes);
    setProject(p);
  }

  async function handleAssistStream({ mode, prompt }, handlers) {
    const content =
      latestContent.current[activeChapterId] ?? activeChapter?.content ?? "";
    return api.assistStream(
      {
        project_id: projectId,
        chapter_id: activeChapterId,
        mode,
        prompt,
        context_text: content.slice(-2000),
      },
      handlers
    );
  }

  function handleInsert(text) {
    if (!activeChapter) return;
    if (text.includes("**Offline")) return;
    const base =
      latestContent.current[activeChapter.id] ?? activeChapter.content ?? "";
    const next = base
      ? `${base.replace(/\s+$/, "")}\n\n${text.trim()}\n`
      : `${text.trim()}\n`;
    latestContent.current[activeChapter.id] = next;
    setChapters((prev) =>
      prev.map((c) =>
        c.id === activeChapter.id
          ? { ...c, content: next, word_count: countWords(next) }
          : c
      )
    );
    saveChapter(activeChapter.id, { content: next });
  }

  async function handleIndex() {
    setIndexing(true);
    try {
      await api.index(projectId);
    } catch (err) {
      setError(err.message);
    } finally {
      setIndexing(false);
    }
  }

  if (loadState === "loading") {
    return (
      <div className="flex h-full items-center justify-center text-sm text-ink-400">
        Opening manuscript…
      </div>
    );
  }

  if (loadState === "error") {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-3">
        <p className="text-sm text-red-300">{error}</p>
        <button type="button" className="btn-ghost" onClick={onBack}>
          Back to projects
        </button>
      </div>
    );
  }

  return (
    <div className="flex h-full flex-col">
      <header className="flex items-center justify-between border-b border-panel-border bg-panel/40 px-4 py-2">
        <div className="flex items-center gap-3">
          <span className="font-serif text-sm text-accent">GhostWriter</span>
          {project?.genre && (
            <span className="rounded-full border border-panel-border px-2 py-0.5 font-mono text-[10px] text-ink-500">
              {project.genre}
            </span>
          )}
        </div>
        <div className="flex items-center gap-2">
          <StatusPill label="API" ok title="Backend reachable" />
          <StatusPill
            label="LLM"
            ok={!!health?.llm_available}
            title={
              health?.llm_available
                ? "Language model connected"
                : "No LLM — offline helpers active"
            }
          />
          <StatusPill
            label="Memory"
            ok={!!health?.embedding_ready}
            title={
              health?.embedding_ready
                ? "Embeddings ready for RAG"
                : "Embeddings loading or unavailable"
            }
          />
        </div>
      </header>

      {error && (
        <div className="border-b border-red-900/40 bg-red-950/30 px-4 py-1.5 text-xs text-red-200">
          {error}
          <button type="button" className="ml-3 underline" onClick={() => setError("")}>
            dismiss
          </button>
        </div>
      )}

      <div className="flex min-h-0 flex-1">
        <ChapterSidebar
          project={project}
          chapters={chapters}
          activeChapterId={activeChapterId}
          onSelect={setActiveChapterId}
          onAdd={handleAddChapter}
          onDelete={handleDeleteChapter}
          onBack={onBack}
        />

        <Editor
          chapter={activeChapter}
          saving={saving}
          onChangeTitle={(title) => {
            if (!activeChapter) return;
            setChapters((prev) =>
              prev.map((c) => (c.id === activeChapter.id ? { ...c, title } : c))
            );
            saveChapter(activeChapter.id, { title });
          }}
          onChangeContent={(content) => {
            if (!activeChapter) return;
            latestContent.current[activeChapter.id] = content;
            const word_count = countWords(content);
            setChapters((prev) =>
              prev.map((c) =>
                c.id === activeChapter.id ? { ...c, content, word_count } : c
              )
            );
            saveChapter(activeChapter.id, { content });
          }}
        />

        <aside className="flex w-[400px] shrink-0 flex-col border-l border-panel-border bg-panel/60">
          <div className="flex border-b border-panel-border">
            {[
              ["ai", "AI"],
              ["map", "Map"],
              ["characters", "Cast"],
              ["world", "World"],
            ].map(([id, label]) => (
              <button
                key={id}
                type="button"
                onClick={() => setRightTab(id)}
                className={`flex-1 py-2.5 text-xs font-medium transition ${
                  rightTab === id
                    ? "border-b-2 border-accent text-accent-glow"
                    : "text-ink-500 hover:text-ink-200"
                }`}
              >
                {label}
              </button>
            ))}
          </div>
          <div className="min-h-0 flex-1">
            {rightTab === "ai" && (
              <AssistPanel
                onAssistStream={handleAssistStream}
                onInsert={handleInsert}
                onIndex={handleIndex}
                llmAvailable={!!health?.llm_available}
                indexing={indexing}
              />
            )}
            {rightTab === "map" && (
              <StoryMap
                chapters={chapters}
                characters={characters}
                activeChapterId={activeChapterId}
                onSelectChapter={setActiveChapterId}
              />
            )}
            {rightTab === "characters" && (
              <CharacterPanel
                characters={characters}
                onCreate={handleCreateCharacter}
                onUpdate={handleUpdateCharacter}
                onDelete={handleDeleteCharacter}
              />
            )}
            {rightTab === "world" && (
              <WorldNotes
                notes={project?.world_notes || ""}
                onSave={handleSaveWorld}
              />
            )}
          </div>
        </aside>
      </div>
    </div>
  );
}
