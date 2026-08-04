import { useEffect, useRef, useState } from "react";
import { api } from "../api";

const RATES = [
  { value: 0.75, label: "0.75×" },
  { value: 0.9, label: "0.9×" },
  { value: 1.0, label: "1.0×" },
  { value: 1.25, label: "1.25×" },
];

function SpeakerIcon() {
  return (
    <svg
      viewBox="0 0 16 16"
      width="13"
      height="13"
      fill="currentColor"
      aria-hidden="true"
    >
      <path d="M8 2.2 4.9 5H2.2A.6.6 0 0 0 1.6 5.6v4.8c0 .33.27.6.6.6h2.7L8 13.8c.3.3.8.1.8-.3V2.5c0-.4-.5-.6-.8-.3Z" />
      <path
        d="M10.2 5.4a.55.55 0 0 1 .8-.1 4.6 4.6 0 0 1 0 5.4.55.55 0 0 1-.8-.1.55.55 0 0 1 .1-.8 3.5 3.5 0 0 0 0-3.6.55.55 0 0 1-.1-.8Z"
        opacity="0.7"
      />
    </svg>
  );
}

export default function Editor({
  chapter,
  saving,
  projectId,
  pacing,
  onPacingChange,
  onChangeTitle,
  onChangeContent,
}) {
  const [title, setTitle] = useState(chapter?.title || "");
  const [content, setContent] = useState(chapter?.content || "");
  const textareaRef = useRef(null);
  const voicesRef = useRef([]);
  const spokenRef = useRef(null);
  const audioRef = useRef(null);
  const [speaking, setSpeaking] = useState(false);
  const [rate, setRate] = useState(0.9);
  const [ttsStatus, setTtsStatus] = useState("unknown"); // unknown | ready | unavailable
  const [ttsError, setTtsError] = useState("");
  const [pacingOpen, setPacingOpen] = useState(false);

  const supported =
    typeof window !== "undefined" && "speechSynthesis" in window;

  useEffect(() => {
    let cancelled = false;
    if (projectId) {
      api
        .ttsStatus(projectId)
        .then((s) => {
          if (cancelled) return;
          setTtsStatus(s?.available ? "ready" : "unavailable");
        })
        .catch(() => {
          if (!cancelled) setTtsStatus("unavailable");
        });
    } else {
      setTtsStatus("unavailable");
    }
    return () => {
      cancelled = true;
    };
  }, [projectId]);

  function stopSpeaking() {
    if (audioRef.current) {
      audioRef.current.pause();
      audioRef.current.currentTime = 0;
    }
    if (supported) window.speechSynthesis.cancel();
    setSpeaking(false);
  }

  function pickVoice() {
    const voices = voicesRef.current;
    if (!voices.length) return null;
    const en = voices.filter((v) => v.lang.toLowerCase().startsWith("en"));
    const pool = en.length ? en : voices;
    return (
      pool.find((v) =>
        /natural|premium|samantha|google|aria|jenny|sonia|zira|libby|matilda|emily|karen|daniel/i.test(
          v.name
        )
      ) || pool[0]
    );
  }

  function speakWithOs(text) {
    if (!supported) return;
    window.speechSynthesis.cancel();
    const utter = new SpeechSynthesisUtterance(text);
    utter.rate = rate;
    const voice = pickVoice();
    if (voice) utter.voice = voice;
    utter.onend = () => setSpeaking(false);
    utter.onerror = () => setSpeaking(false);
    window.speechSynthesis.speak(utter);
    setSpeaking(true);
  }

  async function speakWithPiper(text) {
    setSpeaking(true);
    setTtsError("");
    try {
      const blob = await api.ttsPreview(projectId, text, pacing);
      const url = URL.createObjectURL(blob);
      const audio = audioRef.current;
      if (!audio) return;
      audio.src = url;
      audio.playbackRate = rate;
      await audio.play();
      audio.onended = () => {
        setSpeaking(false);
        URL.revokeObjectURL(url);
      };
      audio.onerror = () => {
        setSpeaking(false);
        URL.revokeObjectURL(url);
      };
    } catch (err) {
      setTtsError(err?.message || "TTS preview failed");
      setSpeaking(false);
    }
  }

  function speak() {
    const ta = textareaRef.current;
    const raw = ta ? ta.value : content;
    const start = ta ? ta.selectionStart : 0;
    const end = ta ? ta.selectionEnd : 0;
    const hasSelection = ta && end > start;
    const text = (hasSelection ? raw.slice(start, end) : raw).trim();
    if (!text) return;

    if (ttsStatus === "ready" && projectId && text.length <= 5000) {
      // natural voice: read the selection — the "does it sound right" case
      speakWithPiper(text);
    } else {
      speakWithOs(text);
    }
  }

  useEffect(() => {
    setTitle(chapter?.title || "");
    setContent(chapter?.content || "");
    stopSpeaking();
  }, [chapter?.id]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (!supported) return;
    const load = () => {
      voicesRef.current = window.speechSynthesis.getVoices();
    };
    load();
    window.speechSynthesis.addEventListener("voiceschanged", load);
    return () => {
      window.speechSynthesis.removeEventListener("voiceschanged", load);
      window.speechSynthesis.cancel();
    };
  }, [supported]);

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
          {ttsStatus === "ready" && (
            <span
              className="rounded-full border border-accent/30 px-2 py-0.5 text-accent"
              title="Natural local voice (piper) active for Listen"
            >
              Voice
            </span>
          )}
          {ttsError && <span className="text-red-300">{ttsError}</span>}
          {(supported || ttsStatus === "ready") && (
            <div className="flex items-center gap-1.5">
              <button
                type="button"
                className={`btn-ghost px-2 py-1 text-xs ${
                  speaking ? "text-red-300" : ""
                }`}
                title={
                  speaking
                    ? "Stop reading"
                    : ttsStatus === "ready"
                    ? "Read aloud in a natural voice (reads the selected text if any)"
                    : "Read the chapter aloud with the system voice (reads the selected text if any)"
                }
                onClick={() => (speaking ? stopSpeaking() : speak())}
                disabled={!content.trim()}
              >
                {speaking ? (
                  <span className="flex items-center gap-1.5">
                    <span className="inline-block h-2 w-2 rounded-full bg-red-400" />
                    Stop
                  </span>
                ) : (
                  <span className="flex items-center gap-1.5">
                    <SpeakerIcon />
                    Listen
                  </span>
                )}
              </button>
              <select
                value={rate}
                onChange={(e) => setRate(Number(e.target.value))}
                className="cursor-pointer rounded border border-panel-border bg-panel/60 px-1.5 py-1 text-[11px] text-ink-300 hover:bg-panel-raised focus:outline-none"
                title="Reading speed"
                disabled={speaking}
              >
                {RATES.map((r) => (
                  <option key={r.value} value={r.value}>
                    {r.label}
                  </option>
                ))}
              </select>
              {ttsStatus === "ready" && (
                <button
                  type="button"
                  className={`btn-ghost px-2 py-1 text-xs ${pacingOpen ? "text-accent-glow" : ""}`}
                  onClick={() => setPacingOpen((v) => !v)}
                  title="Adjust pauses between paragraphs/scenes and the voice's speaking rate"
                >
                  Pacing
                </button>
              )}
            </div>
          )}
          <span>{words.toLocaleString()} words</span>
          <span className={saving ? "text-accent" : "text-ink-600"}>
            {saving ? "Saving…" : "Saved"}
          </span>
        </div>
      </div>

      {pacingOpen && ttsStatus === "ready" && (
        <div className="flex flex-wrap items-center gap-x-5 gap-y-2 border-b border-panel-border bg-panel/40 px-6 py-2.5">
          {[
            ["paragraph_pause", "Paragraph pause", 0, 2, 0.05, "s"],
            ["scene_pause", "Scene break pause", 0, 4, 0.1, "s"],
            ["chapter_pause", "Chapter pause", 0, 4, 0.1, "s"],
            ["speech_rate", "Speaking rate", 0.5, 1.9, 0.05, "×"],
          ].map(([key, label, min, max, step, unit]) => (
            <label key={key} className="flex items-center gap-2 text-[11px] text-ink-400">
              <span className="w-28 shrink-0">{label}</span>
              <input
                type="range"
                className="w-32 accent-[#c4a35a]"
                min={min}
                max={max}
                step={step}
                value={(pacing || {})[key]}
                onChange={(e) =>
                  onPacingChange?.((prev) => ({
                    ...(prev || {}),
                    [key]: Number(e.target.value),
                  }))
                }
                disabled={speaking}
              />
              <span className="w-16 font-mono text-ink-300">
                {pacing[key].toFixed(2)}
                <span className="ml-0.5 text-ink-600">{unit}</span>
              </span>
            </label>
          ))}
        </div>
      )}
      <textarea
        ref={textareaRef}
        className="editor-area min-h-0 flex-1 resize-none bg-transparent px-6 py-6 text-ink-100 placeholder:text-ink-700 focus:outline-none md:px-12 lg:px-16"
        value={content}
        onChange={(e) => {
          setContent(e.target.value);
          onChangeContent(e.target.value);
        }}
        placeholder="Begin writing…"
        spellCheck
      />
      <audio ref={audioRef} className="hidden" />
    </div>
  );
}
