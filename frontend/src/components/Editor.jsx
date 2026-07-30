import { useEffect, useState } from "react";

export default function Editor({
  chapter,
  saving,
  onChangeTitle,
  onChangeContent,
}) {
  const [title, setTitle] = useState(chapter?.title || "");
  const [content, setContent] = useState(chapter?.content || "");

  useEffect(() => {
    setTitle(chapter?.title || "");
    setContent(chapter?.content || "");
  }, [chapter?.id]); // eslint-disable-line react-hooks/exhaustive-deps

  if (!chapter) {
    return (
      <div className="flex h-full flex-1 items-center justify-center text-ink-500">
        <div className="text-center">
          <p className="font-serif text-xl text-ink-300">Select or create a chapter</p>
          <p className="mt-2 text-sm">Your manuscript lives here — distraction-free.</p>
        </div>
      </div>
    );
  }

  const words = content.trim() ? content.trim().split(/\s+/).length : 0;

  return (
    <div className="flex h-full min-w-0 flex-1 flex-col">
      <div className="flex items-center justify-between border-b border-panel-border px-6 py-3">
        <input
          className="w-full bg-transparent font-serif text-xl text-ink-50 placeholder:text-ink-600 focus:outline-none"
          value={title}
          onChange={(e) => {
            setTitle(e.target.value);
            onChangeTitle(e.target.value);
          }}
          placeholder="Chapter title"
        />
        <div className="ml-4 flex shrink-0 items-center gap-3 font-mono text-[11px] text-ink-500">
          <span>{words.toLocaleString()} words</span>
          <span className={saving ? "text-accent" : "text-ink-600"}>
            {saving ? "Saving…" : "Saved"}
          </span>
        </div>
      </div>
      <textarea
        className="editor-area min-h-0 flex-1 resize-none bg-transparent px-6 py-6 text-ink-100 placeholder:text-ink-700 focus:outline-none md:px-12 lg:px-16"
        value={content}
        onChange={(e) => {
          setContent(e.target.value);
          onChangeContent(e.target.value);
        }}
        placeholder="Begin writing…"
        spellCheck
      />
    </div>
  );
}
