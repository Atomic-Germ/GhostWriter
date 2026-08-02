import { useEffect, useState } from "react";
import { useDebouncedCallback } from "../hooks/useDebouncedCallback";

export default function WorldNotes({
  notes,
  series = "",
  seriesList = [],
  onSave,
  onChangeSeries,
}) {
  const [value, setValue] = useState(notes || "");
  const [saving, setSaving] = useState(false);
  const [seriesInput, setSeriesInput] = useState(series || "");
  const [clearingSeries, setClearingSeries] = useState(false);

  useEffect(() => {
    setValue(notes || "");
  }, [notes]);

  useEffect(() => {
    setSeriesInput(series || "");
  }, [series]);

  async function handleSaveSeries() {
    const next = seriesInput.trim();
    if (next === (series || "").trim()) return;
    try {
      await onChangeSeries(next);
    } catch {
      setSeriesInput(series || "");
    }
  }

  const debouncedSave = useDebouncedCallback(async (text) => {
    setSaving(true);
    try {
      await onSave(text);
    } finally {
      setSaving(false);
    }
  }, 800);

  return (
    <div className="flex h-full flex-col">
      <div className="flex items-center justify-between border-b border-panel-border px-3 py-2">
        <span className="panel-title">World & lore</span>
        <span className="font-mono text-[10px] text-ink-600">
          {saving ? "Saving…" : "Auto-save"}
        </span>
      </div>
      <div className="border-b border-panel-border px-3 py-2">
        <label className="label">Universe / series</label>
        <div className="flex gap-2">
          <input
            className="input"
            list="ghostwriter-series-select"
            value={seriesInput}
            onChange={(e) => setSeriesInput(e.target.value)}
            placeholder={seriesList.length ? "Pick a series or type a new one" : "e.g. The Drowned Chronicles"}
          />
          <button
            type="button"
            className="btn-primary shrink-0 px-2 py-1 text-xs"
            disabled={seriesInput.trim() === (series || "").trim()}
            onClick={handleSaveSeries}
          >
            Set
          </button>
        </div>
        <datalist id="ghostwriter-series-select">
          {seriesList.map((name) => (
            <option key={name} value={name} />
          ))}
        </datalist>
        <div className="mt-1.5 flex items-center justify-between">
          <span className="text-[11px] text-ink-500">
            {series
              ? `This book belongs to “${series}”`
              : "Standalone — not part of any universe"}
          </span>
          {series.trim() && (
            <button
              type="button"
              className="text-[11px] text-ink-500 underline hover:text-red-300"
              onClick={async () => {
                try {
                  await onChangeSeries("");
                } catch {
                  /* keep current */
                }
              }}
            >
              Remove from series
            </button>
          )}
        </div>
      </div>
      <textarea
        className="min-h-0 flex-1 resize-none bg-transparent p-3 text-xs leading-relaxed text-ink-200 placeholder:text-ink-600 focus:outline-none"
        value={value}
        onChange={(e) => {
          setValue(e.target.value);
          debouncedSave(e.target.value);
        }}
        placeholder="Magic systems, places, history, rules of the world…"
      />
    </div>
  );
}
