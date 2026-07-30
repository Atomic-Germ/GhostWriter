import { useEffect, useState } from "react";
import { useDebouncedCallback } from "../hooks/useDebouncedCallback";

export default function WorldNotes({ notes, onSave }) {
  const [value, setValue] = useState(notes || "");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    setValue(notes || "");
  }, [notes]);

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
