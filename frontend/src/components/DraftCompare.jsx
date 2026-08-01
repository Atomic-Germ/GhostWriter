import { useEffect, useState } from "react";
import { api } from "../api";

function wordDiff(left, right) {
  const lw = left.split(/\s+/);
  const rw = right.split(/\s+/);
  const m = lw.length;
  const n = rw.length;
  if (m === 0 && n === 0) return [];
  if (m === 0) return rw.map((w) => ({ type: "add", word: w }));
  if (n === 0) return lw.map((w) => ({ type: "remove", word: w }));

  const dp = Array.from({ length: m + 1 }, () => new Uint16Array(n + 1));
  for (let i = 1; i <= m; i++) {
    for (let j = 1; j <= n; j++) {
      if (lw[i - 1] === rw[j - 1]) {
        dp[i][j] = dp[i - 1][j - 1] + 1;
      } else {
        dp[i][j] = Math.max(dp[i - 1][j], dp[i][j - 1]);
      }
    }
  }

  const result = [];
  let i = m,
    j = n;
  while (i > 0 || j > 0) {
    if (i > 0 && j > 0 && lw[i - 1] === rw[j - 1]) {
      result.unshift({ type: "equal", word: lw[i - 1] });
      i--;
      j--;
    } else if (j > 0 && (i === 0 || dp[i][j - 1] >= dp[i - 1][j])) {
      result.unshift({ type: "add", word: rw[j - 1] });
      j--;
    } else {
      result.unshift({ type: "remove", word: lw[i - 1] });
      i--;
    }
  }
  return result;
}

function DiffView({ left, right }) {
  if (!left && !right) return <p className="text-sm text-ink-500">No content.</p>;
  const diff = wordDiff(left || "", right || "");
  return (
    <div className="flex gap-4 text-sm font-mono leading-relaxed">
      <div className="flex-1 rounded-lg border border-panel-border bg-ink-950/40 p-3">
        <div className="mb-2 font-sans text-xs uppercase tracking-wide text-ink-500">
          Original
        </div>
        {diff.map((item, idx) => {
          if (item.type === "remove") {
            return (
              <mark
                key={idx}
                className="bg-red-950/60 text-red-300 decoration-red-400 underline decoration-wavy"
              >
                {item.word}{" "}
              </mark>
            );
          }
          if (item.type === "add") {
            return (
              <span className="text-ink-600" key={idx}>
                {item.word}{" "}
              </span>
            );
          }
          return (
            <span key={idx} className="text-ink-200">
              {item.word}{" "}
            </span>
          );
        })}
      </div>
      <div className="flex-1 rounded-lg border border-panel-border bg-ink-950/40 p-3">
        <div className="mb-2 font-sans text-xs uppercase tracking-wide text-ink-500">
          Fork
        </div>
        {diff.map((item, idx) => {
          if (item.type === "add") {
            return (
              <mark
                key={idx}
                className="bg-accent/20 text-accent-glow"
              >
                {item.word}{" "}
              </mark>
            );
          }
          if (item.type === "remove") {
            return (
              <span className="text-ink-600" key={idx}>
                {item.word}{" "}
              </span>
            );
          }
          return (
            <span key={idx} className="text-ink-200">
              {item.word}{" "}
            </span>
          );
        })}
      </div>
    </div>
  );
}

export default function DraftCompare({ projectId, project }) {
  const [forks, setForks] = useState([]);
  const [loading, setLoading] = useState(true);
  const [leftId, setLeftId] = useState("");
  const [rightId, setRightId] = useState("");
  const [leftChapters, setLeftChapters] = useState([]);
  const [rightChapters, setRightChapters] = useState([]);
  const [leftChapterId, setLeftChapterId] = useState("");
  const [rightChapterId, setRightChapterId] = useState("");
  const [leftContent, setLeftContent] = useState("");
  const [rightContent, setRightContent] = useState("");

  async function loadForks() {
    setLoading(true);
    try {
      const all = await api.listProjects();
      const mine = all.filter((p) => p.fork_of === projectId);
      setForks(mine);
      if (mine.length > 0 && !leftId) {
        setLeftId(mine[0].id);
      }
      if (mine.length > 1 && !rightId) {
        setRightId(mine[1].id);
      }
    } catch {
      /* ignore */
    } finally {
      setLoading(false);
    }
  }

  async function loadChapters(pid, setChapters, setContent) {
    if (!pid) {
      setChapters([]);
      setContent("");
      return;
    }
    try {
      const p = await api.getProject(pid);
      const sorted = [...(p.chapters || [])].sort((a, b) => a.order - b.order);
      setChapters(sorted);
      if (sorted.length > 0 && !leftChapterId && pid === leftId) {
        setLeftChapterId(sorted[0].id);
        setContent(sorted[0].content || "");
      }
      if (sorted.length > 0 && !rightChapterId && pid === rightId) {
        setRightChapterId(sorted[0].id);
        setContent(sorted[0].content || "");
      }
    } catch {
      /* ignore */
    }
  }

  useEffect(() => {
    loadForks();
  }, [projectId]);

  useEffect(() => {
    loadChapters(leftId, setLeftChapters, setLeftContent);
  }, [leftId]);

  useEffect(() => {
    loadChapters(rightId, setRightChapters, setRightContent);
  }, [rightId]);

  async function selectLeftChapter(id) {
    setLeftChapterId(id);
    const ch = leftChapters.find((c) => c.id === id);
    setLeftContent(ch?.content || "");
  }

  async function selectRightChapter(id) {
    setRightChapterId(id);
    const ch = rightChapters.find((c) => c.id === id);
    setRightContent(ch?.content || "");
  }

  return (
    <div className="flex flex-col gap-3 p-3">
      <div className="flex items-center justify-between">
        <span className="panel-title">Draft comparison</span>
        <button
          type="button"
          className="btn-ghost px-2 py-1 text-[11px]"
          onClick={loadForks}
          title="Refresh fork list"
        >
          ↻ Refresh
        </button>
      </div>

      {loading ? (
        <p className="text-xs text-ink-500">Loading forks…</p>
      ) : forks.length === 0 ? (
        <p className="text-xs text-ink-500">
          No forks yet. Fork this draft to create a new version and compare
          changes.
        </p>
      ) : (
        <>
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="label">Original draft</label>
              <select
                className="input w-full"
                value={leftId}
                onChange={(e) => {
                  setLeftId(e.target.value);
                  setLeftChapterId("");
                  setLeftContent("");
                }}
              >
                <option value="">Select a fork…</option>
                {forks.map((f) => (
                  <option key={f.id} value={f.id}>
                    {f.title} ({f.word_count.toLocaleString()} w)
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="label">Fork to compare</label>
              <select
                className="input w-full"
                value={rightId}
                onChange={(e) => {
                  setRightId(e.target.value);
                  setRightChapterId("");
                  setRightContent("");
                }}
              >
                <option value="">Select a fork…</option>
                {forks
                  .filter((f) => f.id !== leftId)
                  .map((f) => (
                    <option key={f.id} value={f.id}>
                      {f.title} ({f.word_count.toLocaleString()} w)
                    </option>
                  ))}
              </select>
            </div>
          </div>

          {leftId && rightId && (
            <>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="label">Chapter (original)</label>
                  <select
                    className="input w-full"
                    value={leftChapterId}
                    onChange={(e) => selectLeftChapter(e.target.value)}
                  >
                    <option value="">Select…</option>
                    {leftChapters.map((c) => (
                      <option key={c.id} value={c.id}>
                        {c.title}
                      </option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="label">Chapter (fork)</label>
                  <select
                    className="input w-full"
                    value={rightChapterId}
                    onChange={(e) => selectRightChapter(e.target.value)}
                  >
                    <option value="">Select…</option>
                    {rightChapters.map((c) => (
                      <option key={c.id} value={c.id}>
                        {c.title}
                      </option>
                    ))}
                  </select>
                </div>
              </div>

              {leftChapterId && rightChapterId && (
                <div className="mt-2">
                  <DiffView left={leftContent} right={rightContent} />
                </div>
              )}
            </>
          )}
        </>
      )}
    </div>
  );
}