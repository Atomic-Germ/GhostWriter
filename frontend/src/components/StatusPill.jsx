export default function StatusPill({ label, ok, title }) {
  return (
    <span
      title={title}
      className="inline-flex items-center gap-1.5 rounded-full border border-panel-border bg-panel-raised/80 px-2.5 py-1 text-[11px] text-ink-300"
    >
      <span
        className={`h-1.5 w-1.5 rounded-full ${ok ? "bg-emerald-400 shadow-[0_0_8px_#34d399]" : "bg-ink-500"}`}
      />
      {label}
    </span>
  );
}
