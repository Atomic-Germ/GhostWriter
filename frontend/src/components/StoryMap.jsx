import { useMemo, useState } from "react";
import { buildStoryMap } from "../lib/storyMetrics";

function heatColor(t) {
  // cool ink → accent gold
  const x = Math.max(0, Math.min(1, t));
  const r = Math.round(60 + x * 140);
  const g = Math.round(55 + x * 90);
  const b = Math.round(45 + x * 20);
  return `rgb(${r},${g},${b})`;
}

function TensionChart({ chapters, activeId, onSelect }) {
  const w = 320;
  const h = 88;
  const pad = 8;
  if (!chapters.length) return null;

  const pts = chapters.map((ch, i) => {
    const x =
      pad + (chapters.length === 1 ? w / 2 - pad : (i / (chapters.length - 1)) * (w - pad * 2));
    const y = h - pad - ch.tension * (h - pad * 2);
    return { x, y, ch };
  });

  const line = pts.map((p, i) => `${i === 0 ? "M" : "L"} ${p.x.toFixed(1)} ${p.y.toFixed(1)}`).join(" ");
  const area =
    pts.length > 0
      ? `${line} L ${pts[pts.length - 1].x.toFixed(1)} ${h - pad} L ${pts[0].x.toFixed(1)} ${h - pad} Z`
      : "";

  return (
    <svg viewBox={`0 0 ${w} ${h}`} className="w-full" role="img" aria-label="Tension curve">
      <defs>
        <linearGradient id="tensionFill" x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor="#c4a35a" stopOpacity="0.35" />
          <stop offset="100%" stopColor="#c4a35a" stopOpacity="0" />
        </linearGradient>
      </defs>
      {/* guide lines */}
      {[0.25, 0.5, 0.75].map((g) => (
        <line
          key={g}
          x1={pad}
          x2={w - pad}
          y1={h - pad - g * (h - pad * 2)}
          y2={h - pad - g * (h - pad * 2)}
          stroke="#3a342c"
          strokeDasharray="3 4"
        />
      ))}
      <path d={area} fill="url(#tensionFill)" />
      <path d={line} fill="none" stroke="#c4a35a" strokeWidth="2" strokeLinejoin="round" />
      {pts.map(({ x, y, ch }) => (
        <g key={ch.id} className="cursor-pointer" onClick={() => onSelect?.(ch.id)}>
          <circle
            cx={x}
            cy={y}
            r={ch.id === activeId ? 5.5 : 3.5}
            fill={ch.id === activeId ? "#e8d5a3" : "#c4a35a"}
            stroke="#16140f"
            strokeWidth="1"
          />
          <title>
            {ch.title}: heat {(ch.tension * 100).toFixed(0)}% · {ch.words} words
          </title>
        </g>
      ))}
    </svg>
  );
}

function StoryCircle({ chapters, activeId, onSelect }) {
  const cx = 110;
  const cy = 110;
  const r = 78;
  const beats = useMemo(() => {
    // group chapters onto 8 slots by their assigned beat
    const map = {};
    for (const ch of chapters) {
      const id = ch.beat.id;
      if (!map[id]) map[id] = [];
      map[id].push(ch);
    }
    return map;
  }, [chapters]);

  const uniqueBeats = chapters.length
    ? [...new Map(chapters.map((c) => [c.beat.id, c.beat])).values()]
    : [];

  // Always draw full circle labels
  const labels = [
    { id: "you", label: "You" },
    { id: "need", label: "Need" },
    { id: "go", label: "Go" },
    { id: "search", label: "Search" },
    { id: "find", label: "Find" },
    { id: "take", label: "Take" },
    { id: "return", label: "Return" },
    { id: "change", label: "Change" },
  ];

  return (
    <div className="flex flex-col items-center gap-2">
      <svg viewBox="0 0 220 220" className="w-full max-w-[240px]" aria-label="Story circle">
        <circle cx={cx} cy={cy} r={r} fill="none" stroke="#3a342c" strokeWidth="1.5" />
        <circle cx={cx} cy={cy} r={r * 0.55} fill="none" stroke="#3a342c" strokeDasharray="2 4" />
        {labels.map((b, i) => {
          const ang = -Math.PI / 2 + (i / labels.length) * Math.PI * 2;
          const lx = cx + Math.cos(ang) * (r + 22);
          const ly = cy + Math.sin(ang) * (r + 22);
          const onRing = beats[b.id] || [];
          const active = onRing.some((c) => c.id === activeId);
          return (
            <g key={b.id}>
              <line
                x1={cx + Math.cos(ang) * (r - 6)}
                y1={cy + Math.sin(ang) * (r - 6)}
                x2={cx + Math.cos(ang) * (r + 6)}
                y2={cy + Math.sin(ang) * (r + 6)}
                stroke={onRing.length ? "#c4a35a" : "#3a342c"}
                strokeWidth={onRing.length ? 2 : 1}
              />
              <text
                x={lx}
                y={ly}
                textAnchor="middle"
                dominantBaseline="middle"
                className="fill-ink-400"
                style={{ fontSize: 9, fontFamily: "IBM Plex Mono, monospace" }}
                fill={active ? "#e8d5a3" : onRing.length ? "#c4a35a" : "#7f725c"}
              >
                {b.label}
              </text>
              {onRing.map((ch, j) => {
                const rr = r * (0.72 - j * 0.12);
                const px = cx + Math.cos(ang) * rr;
                const py = cy + Math.sin(ang) * rr;
                return (
                  <circle
                    key={ch.id}
                    cx={px}
                    cy={py}
                    r={ch.id === activeId ? 6 : 4.5}
                    fill={heatColor(ch.tension)}
                    stroke={ch.id === activeId ? "#e8d5a3" : "#16140f"}
                    strokeWidth={ch.id === activeId ? 1.5 : 1}
                    className="cursor-pointer"
                    onClick={() => onSelect?.(ch.id)}
                  >
                    <title>
                      {ch.title} · {ch.beat.label}: {ch.beat.hint}
                    </title>
                  </circle>
                );
              })}
            </g>
          );
        })}
        <text
          x={cx}
          y={cy}
          textAnchor="middle"
          dominantBaseline="middle"
          fill="#7f725c"
          style={{ fontSize: 10, fontFamily: "Literata, serif" }}
        >
          circle
        </text>
      </svg>
      {uniqueBeats.length > 0 && (
        <p className="px-1 text-center font-mono text-[10px] text-ink-500">
          Chapters placed by position along an 8-beat circle (soft guide, not a verdict).
        </p>
      )}
    </div>
  );
}

function PresenceGrid({ chapters, characters, activeId, onSelect }) {
  if (!characters.length || !chapters.length) {
    return (
      <p className="text-xs text-ink-500">
        Add character dossiers and write names into chapters to see presence.
      </p>
    );
  }

  const maxMention = Math.max(
    1,
    ...chapters.flatMap((ch) => characters.map((c) => ch.presence[c.id] || 0))
  );

  return (
    <div className="overflow-x-auto">
      <table className="w-full border-collapse text-left">
        <thead>
          <tr>
            <th className="sticky left-0 bg-panel/90 py-1 pr-2 font-mono text-[9px] uppercase tracking-wide text-ink-500">
              Cast
            </th>
            {chapters.map((ch, i) => (
              <th key={ch.id} className="px-0.5 py-1 text-center">
                <button
                  type="button"
                  onClick={() => onSelect?.(ch.id)}
                  className={`font-mono text-[9px] ${
                    ch.id === activeId ? "text-accent-glow" : "text-ink-500 hover:text-ink-300"
                  }`}
                  title={ch.title}
                >
                  {i + 1}
                </button>
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {characters.map((c) => (
            <tr key={c.id} className="border-t border-panel-border/60">
              <td className="sticky left-0 max-w-[88px] truncate bg-panel/90 py-1 pr-2 font-mono text-[10px] text-ink-300">
                {c.name}
              </td>
              {chapters.map((ch) => {
                const n = ch.presence[c.id] || 0;
                const t = n / maxMention;
                return (
                  <td key={ch.id} className="px-0.5 py-1">
                    <button
                      type="button"
                      onClick={() => onSelect?.(ch.id)}
                      className="mx-auto block h-5 w-5 rounded-sm border border-transparent transition hover:border-accent/40"
                      style={{
                        background:
                          n === 0 ? "#1c1915" : `rgba(196, 163, 90, ${0.15 + t * 0.75})`,
                      }}
                      title={`${c.name} in ${ch.title}: ${n} mention${n === 1 ? "" : "s"}`}
                    />
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function WordBars({ chapters, maxWords, activeId, onSelect }) {
  return (
    <div className="space-y-1.5">
      {chapters.map((ch, i) => (
        <button
          key={ch.id}
          type="button"
          onClick={() => onSelect?.(ch.id)}
          className={`flex w-full items-center gap-2 rounded-md px-1 py-0.5 text-left transition hover:bg-panel-raised ${
            ch.id === activeId ? "bg-accent/10" : ""
          }`}
        >
          <span className="w-5 shrink-0 font-mono text-[10px] text-ink-600">{i + 1}</span>
          <span className="w-20 shrink-0 truncate font-mono text-[10px] text-ink-400" title={ch.title}>
            {ch.title}
          </span>
          <div className="h-2 min-w-0 flex-1 overflow-hidden rounded-full bg-ink-950">
            <div
              className="h-full rounded-full bg-accent/70"
              style={{ width: `${Math.max(ch.empty ? 0 : 4, (ch.words / maxWords) * 100)}%` }}
            />
          </div>
          <span className="w-10 shrink-0 text-right font-mono text-[10px] text-ink-500">
            {ch.words}
          </span>
        </button>
      ))}
    </div>
  );
}

function ArcLanes({ arcs, chapterCount, chapters, onSelect }) {
  if (!arcs.length) return null;
  const active = arcs.filter((a) => a.total > 0);
  if (!active.length) {
    return (
      <p className="text-xs text-ink-500">
        No name hits yet — presence uses dossier names in the prose.
      </p>
    );
  }

  const denom = Math.max(1, chapterCount - 1);

  return (
    <div className="space-y-2">
      {active.map((a) => (
        <div key={a.id}>
          <div className="mb-0.5 flex justify-between font-mono text-[10px]">
            <span className="truncate text-ink-300">{a.name}</span>
            <span className="text-ink-600">{a.total}×</span>
          </div>
          <div className="relative h-3 rounded-full bg-ink-950">
            <div
              className="absolute top-0.5 h-2 rounded-full bg-accent/25"
              style={{
                left: chapterCount <= 1 ? "0%" : `${(a.first / denom) * 100}%`,
                width:
                  chapterCount <= 1
                    ? "100%"
                    : `${Math.max(4, ((a.span - 1) / denom) * 100)}%`,
              }}
            />
            {chapters.map((ch, i) => {
              const n = ch.presence[a.id] || 0;
              if (!n) return null;
              const left = chapterCount <= 1 ? 50 : (i / denom) * 100;
              return (
                <button
                  key={ch.id}
                  type="button"
                  onClick={() => onSelect?.(ch.id)}
                  className="absolute top-0.5 h-2 w-2 -translate-x-1/2 rounded-full bg-accent hover:ring-1 hover:ring-accent-glow"
                  style={{ left: `${left}%`, opacity: 0.45 + Math.min(0.55, n / 8) }}
                  title={`${a.name} · ${ch.title}: ${n}`}
                />
              );
            })}
          </div>
        </div>
      ))}
    </div>
  );
}

export default function StoryMap({ chapters, characters, activeChapterId, onSelectChapter }) {
  const [view, setView] = useState("overview"); // overview | circle | links
  const map = useMemo(
    () => buildStoryMap(chapters, characters),
    [chapters, characters]
  );

  if (!map.chapters.length) {
    return (
      <div className="flex h-full flex-col items-center justify-center gap-2 p-6 text-center">
        <p className="font-serif text-base text-ink-300">Story map</p>
        <p className="text-xs text-ink-500">Add a chapter to see structure emerge.</p>
      </div>
    );
  }

  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center justify-between border-b border-panel-border px-3 py-2">
        <span className="panel-title">Story map</span>
        <span className="font-mono text-[10px] text-ink-600">
          {map.totalWords.toLocaleString()} w · {map.chapters.length} ch
        </span>
      </div>

      <div className="flex gap-1 border-b border-panel-border px-2 py-1.5">
        {[
          ["overview", "Overview"],
          ["circle", "Circle"],
          ["links", "Links"],
        ].map(([id, label]) => (
          <button
            key={id}
            type="button"
            onClick={() => setView(id)}
            className={`rounded-md px-2 py-1 text-[11px] ${
              view === id
                ? "bg-accent/20 text-accent-glow"
                : "text-ink-500 hover:bg-panel-raised hover:text-ink-200"
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      <div className="min-h-0 flex-1 space-y-5 overflow-y-auto p-3">
        {view === "overview" && (
          <>
            <section>
              <h3 className="panel-title mb-2">Dramatic pulse</h3>
              <p className="mb-2 font-mono text-[10px] text-ink-600">
                Local heat from dialogue, pacing, and charged diction — a glance, not a grade.
              </p>
              <TensionChart
                chapters={map.chapters}
                activeId={activeChapterId}
                onSelect={onSelectChapter}
              />
            </section>

            <section>
              <h3 className="panel-title mb-2">Chapter mass</h3>
              <WordBars
                chapters={map.chapters}
                maxWords={map.maxWords}
                activeId={activeChapterId}
                onSelect={onSelectChapter}
              />
            </section>

            <section>
              <h3 className="panel-title mb-2">Presence</h3>
              <PresenceGrid
                chapters={map.chapters}
                characters={map.characters}
                activeId={activeChapterId}
                onSelect={onSelectChapter}
              />
            </section>

            <section>
              <h3 className="panel-title mb-2">Character arcs</h3>
              <ArcLanes
                arcs={map.arcs}
                chapterCount={map.chapters.length}
                chapters={map.chapters}
                onSelect={onSelectChapter}
              />
            </section>
          </>
        )}

        {view === "circle" && (
          <section>
            <h3 className="panel-title mb-1">Narrative circle</h3>
            <p className="mb-3 font-mono text-[10px] leading-relaxed text-ink-600">
              Dan Harmon–style eight beats. Chapters sit by position in the manuscript so you can
              see where mass and heat land — rearrange structure in the editor, not here.
            </p>
            <StoryCircle
              chapters={map.chapters}
              activeId={activeChapterId}
              onSelect={onSelectChapter}
            />
            <ul className="mt-4 space-y-1.5">
              {map.chapters.map((ch, i) => (
                <li key={ch.id}>
                  <button
                    type="button"
                    onClick={() => onSelectChapter?.(ch.id)}
                    className={`flex w-full items-start gap-2 rounded-md px-2 py-1.5 text-left text-xs transition hover:bg-panel-raised ${
                      ch.id === activeChapterId ? "bg-accent/10 text-accent-glow" : "text-ink-300"
                    }`}
                  >
                    <span className="font-mono text-[10px] text-ink-600">{i + 1}</span>
                    <span className="min-w-0 flex-1">
                      <span className="block truncate">{ch.title}</span>
                      <span className="font-mono text-[10px] text-ink-500">
                        {ch.beat.label} — {ch.beat.hint}
                      </span>
                    </span>
                    <span
                      className="mt-1 h-2 w-2 shrink-0 rounded-full"
                      style={{ background: heatColor(ch.tension) }}
                    />
                  </button>
                </li>
              ))}
            </ul>
          </section>
        )}

        {view === "links" && (
          <section>
            <h3 className="panel-title mb-1">Who shares the page</h3>
            <p className="mb-3 font-mono text-[10px] text-ink-600">
              Characters that co-appear in the same chapter (by name mention).
            </p>
            {map.edges.length === 0 ? (
              <p className="text-xs text-ink-500">
                No co-presence yet — needs two named characters in one chapter.
              </p>
            ) : (
              <ul className="space-y-2">
                {map.edges.map((e) => (
                  <li
                    key={`${e.a}-${e.b}`}
                    className="rounded-lg border border-panel-border bg-ink-950/40 px-3 py-2"
                  >
                    <div className="flex items-center justify-between gap-2">
                      <span className="text-xs text-ink-200">
                        {e.aName}{" "}
                        <span className="text-ink-600">×</span> {e.bName}
                      </span>
                      <span className="font-mono text-[10px] text-ink-500">
                        {e.chapters} ch · w{e.weight}
                      </span>
                    </div>
                    <div className="mt-1.5 h-1 overflow-hidden rounded-full bg-ink-900">
                      <div
                        className="h-full rounded-full bg-accent/60"
                        style={{
                          width: `${Math.min(100, 20 + e.weight * 8)}%`,
                        }}
                      />
                    </div>
                  </li>
                ))}
              </ul>
            )}
          </section>
        )}
      </div>
    </div>
  );
}
