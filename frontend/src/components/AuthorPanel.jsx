import { useEffect, useState } from "react";
import { useDebouncedCallback } from "../hooks/useDebouncedCallback";

const LANGUAGES = [
  ["en", "English"],
  ["en-US", "English (US)"],
  ["en-GB", "English (UK)"],
  ["fr", "French"],
  ["de", "German"],
  ["es", "Spanish"],
  ["it", "Italian"],
  ["pt", "Portuguese"],
  ["nl", "Dutch"],
];

const FIELDS = [
  ["author", "Author name", "Used as the byline and epub:creator"],
  ["publisher", "Publisher / imprint", "Shown on the copyright page"],
  ["copyright", "Copyright notice", "e.g. “Copyright © 2026 Jane Doe”"],
  ["isbn", "ISBN", "e.g. 9781234567890 (becomes the EPUB identifier)"],
  ["series", "Series", "Book series this title belongs to"],
  ["series_position", "Series number", "Position within the series"],
];

export default function AuthorPanel({ project, onSave }) {
  const [form, setForm] = useState({
    author: "",
    publisher: "",
    copyright: "",
    isbn: "",
    series: "",
    series_position: 0,
    language: "en",
  });
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!project) return;
    setForm({
      author: project.author || "",
      publisher: project.publisher || "",
      copyright: project.copyright || "",
      isbn: project.isbn || "",
      series: project.series || "",
      series_position: project.series_position || 0,
      language: project.language || "en",
    });
  }, [project?.id]); // eslint-disable-line react-hooks/exhaustive-deps

  const debouncedSave = useDebouncedCallback(async (patch) => {
    if (!onSave) return;
    setSaving(true);
    try {
      await onSave(patch);
    } finally {
      setSaving(false);
    }
  }, 600);

  function update(key, value) {
    const next = { ...form, [key]: value };
    setForm(next);
    const patch = {};
    for (const k of Object.keys(next)) {
      if (FIELDS.map((f) => f[0]).includes(k) || k === "language") {
        patch[k] = k === "series_position" ? Number(next[k]) || 0 : next[k];
      }
    }
    debouncedSave(patch);
  }

  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center justify-between border-b border-panel-border px-3 py-2">
        <span className="panel-title">Author & publisher</span>
        <span className="font-mono text-[10px] text-ink-600">
          {saving ? "Saving…" : "Auto-save"}
        </span>
      </div>
      <div className="min-h-0 flex-1 overflow-y-auto p-3">
        <p className="mb-3 text-[11px] leading-relaxed text-ink-500">
          This information is written into the published book — EPUB creator,
          publisher, rights, ISBN, and series metadata.
        </p>
        <div className="space-y-3">
          {FIELDS.map(([key, label, hint]) => (
            <div key={key}>
              <label className="label">{label}</label>
              <input
                className="input text-xs"
                value={form[key]}
                placeholder={hint}
                onChange={(e) => update(key, e.target.value)}
              />
            </div>
          ))}
          <div>
            <label className="label">Language</label>
            <select
              className="input w-full text-xs"
              value={form.language}
              onChange={(e) => update("language", e.target.value)}
            >
              {LANGUAGES.map(([code, label]) => (
                <option key={code} value={code}>
                  {label}
                </option>
              ))}
            </select>
          </div>
        </div>
      </div>
    </div>
  );
}
