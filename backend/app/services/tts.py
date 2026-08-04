"""Local neural text-to-speech (piper-tts) for reading the author's prose aloud.

Two output paths mirror the feature's two use-cases:

* ``preview_text`` — a fast, lightweight clip of a short selection (the "does
  this sound right out loud?" case). Intentionally small and quick, no guardrail.

* ``export_book`` — a full-length audiobook-style WAV of the whole manuscript.
  This is explicitly an *example*, never a deliverable: a spoken disclaimer
  ("This audiobook is not for publication and has been generated with AI") is
  embedded at every chapter start and again roughly every 5 minutes of audio,
  so the file can never be mistaken for a publishable recording.

Intent: help an author hear what their writing sounds like out loud. It never
writes for them; it only reads their own words back in a neutral voice.
"""

import logging
import tempfile
import time
import wave
from pathlib import Path

logger = logging.getLogger("ghostwriter.tts")

VOICE_NAME = "en_US-lessac-medium"

DISCLAIMER = (
    "This audiobook is not for publication, and has been generated with AI."
)
GUARDRAIL_INTERVAL_SEC = 300  # ~5 minutes
# Spoken before the body of each chapter, e.g. "Chapter 3."
CHAPTER_INTRO = "Chapter {n}."

# Scene-break markers common in manuscripts (a paragraph by itself, like * * *).
_SCENE_BREAK_MARKERS = {
    "* * *",
    "***",
    "*** ",
    "—",
    "--",
    "···",
    "· · ·",
}


def _seconds(rate: int, n_samples: int) -> float:
    return n_samples / rate if rate > 0 else 0.0


def _coerce(value, default: float, lo: float, hi: float) -> float:
    """Resolve an optional value, clamping into [lo, hi]."""
    if value is None:
        return default
    try:
        return max(lo, min(hi, float(value)))
    except (TypeError, ValueError):
        return default


def _syn_config(speech_rate: float):
    """Piper synthesis config. rate >1 = faster (shorter phonemes), <1 = slower."""
    from piper import SynthesisConfig

    return SynthesisConfig(length_scale=1.0 / float(speech_rate))


def _silence(rate: int, seconds: float) -> tuple:
    """A silence chunk of the given duration (mono 16-bit)."""
    n = max(0, int(rate * seconds))
    return (b"\x00\x00" * n, rate)


def _is_scene_break(paragraph: str) -> bool:
    return paragraph.strip() in _SCENE_BREAK_MARKERS


def _split_paragraphs(text: str) -> list[str]:
    """Split prose into paragraph units, keeping blank-line breaks."""
    text = (text or "").strip()
    if not text:
        return []
    return [p.strip() for p in text.split("\n\n") if p.strip()]


class Pacing:
    """Timing signals used during synthesis (book-wide, adjustable on the fly)."""

    def __init__(
        self,
        paragraph_pause: float = 0.35,
        scene_pause: float = 1.0,
        chapter_pause: float = 1.4,
        speech_rate: float = 1.0,
    ):
        self.paragraph_pause = _coerce(paragraph_pause, 0.5, lo=0.0, hi=5.0)
        self.scene_pause = _coerce(scene_pause, 1.0, lo=0.0, hi=8.0)
        self.chapter_pause = _coerce(chapter_pause, 1.4, lo=0.0, hi=8.0)
        # >1 faster, <1 slower (clamped to piper's usable range)
        self.speech_rate = _coerce(speech_rate, 1.0, lo=0.5, hi=1.9)

    def as_dict(self) -> dict:
        return {
            "paragraph_pause": self.paragraph_pause,
            "scene_pause": self.scene_pause,
            "chapter_pause": self.chapter_pause,
            "speech_rate": self.speech_rate,
        }


class TTSService:
    def __init__(self, model_dir: Path):
        self._model_dir = model_dir
        self._voice = None

    @property
    def model_path(self) -> Path:
        return self._model_dir / f"{VOICE_NAME}.onnx"

    @property
    def config_path(self) -> Path:
        return self._model_dir / f"{VOICE_NAME}.onnx.json"

    # ── voice loading ──────────────────────────────────────────

    def available(self) -> bool:
        return self.model_path.exists() and self.config_path.exists()

    def ensure_voice(self):
        if self._voice is not None:
            return self._voice
        if not self.available():
            raise RuntimeError(
                "Piper voice not downloaded. Run `python -m app.services.tts "
                "download` or fetch en_US-lessac-medium onnx+json into "
                f"{self._model_dir}"
            )
        from piper import PiperVoice

        t0 = time.time()
        self._voice = PiperVoice.load(str(self.model_path), str(self.config_path))
        logger.info("Loaded TTS voice %s in %.2fs", VOICE_NAME, time.time() - t0)
        return self._voice

    # ── synthesis core ─────────────────────────────────────────

    def synth(self, text: str, pacing: Pacing | None = None) -> list:
        """Synthesize text. Returns list of (pcm_int16_bytes, sample_rate)."""
        voice = self.ensure_voice()
        out: list = []
        rate = float((pacing.speech_rate if pacing else None) or 1.0)
        syn_config = _syn_config(rate) if rate != 1.0 else None
        if syn_config is not None:
            for chunk in voice.synthesize(text, syn_config=syn_config):
                out.append((bytes(chunk.audio_int16_bytes), chunk.sample_rate))
        else:
            for chunk in voice.synthesize(text):
                out.append((bytes(chunk.audio_int16_bytes), chunk.sample_rate))
        return out

    # ── preview clip ───────────────────────────────────────────

    def preview_wav(self, text: str, pacing: Pacing | None = None) -> bytes:
        """Render a short selection to a monophonic 16-bit WAV (no guardrail)."""
        text = (text or "").strip()
        if not text:
            return b""
        pacing = pacing or Pacing()
        pieces: list = []
        paragraphs = _split_paragraphs(text)
        for i, para in enumerate(paragraphs):
            if _is_scene_break(para):
                if pieces:
                    pieces.append(_silence(22050, pacing.scene_pause))
                continue
            pieces.extend(self.synth(para, pacing))
            if i < len(paragraphs) - 1:
                pieces.append(_silence(22050, pacing.paragraph_pause))
        return _wav_bytes_from_chunks(pieces)

    # ── full export (guarded audiobook example) ────────────────

    def guardrail_text(self) -> str:
        return DISCLAIMER

    def guardrail_interval_seconds(self) -> int:
        return GUARDRAIL_INTERVAL_SEC

    def export_book(
        self,
        chapters: list,
        out_path: Path,
        pacing: Pacing | None = None,
    ) -> dict:
        """Synthesize all chapters into a single WAV at ``out_path``.

        Guardrail: a spoken disclaimer is emitted at the start of every chapter
        and again whenever ~5 minutes of audio have accumulated since the last
        one. Returns metadata (chapter count, duration, disclaimer count).
        """
        if not chapters:
            raise ValueError("No chapters to synthesize.")
        pacing = pacing or Pacing()

        disclaimer_chunks = self.synth(DISCLAIMER, pacing)
        disclaimer_rate = disclaimer_chunks[0][1]

        running_sec = 0.0
        last_guard = 0.0
        disclaimer_count = 0

        def emit(chunks: list, tail_pause: float = 0.0) -> None:
            nonlocal running_sec
            for pcm, rate in chunks:
                wr.writeframes(pcm)
                running_sec += _seconds(rate, len(pcm) // 2)
            if tail_pause > 0:
                wr.writeframes(_silence(disclaimer_rate, tail_pause)[0])
                running_sec += tail_pause

        def emit_disclaimer() -> None:
            nonlocal last_guard, disclaimer_count
            emit(disclaimer_chunks)
            last_guard = running_sec
            disclaimer_count += 1

        with wave.open(str(out_path), "wb") as wr:
            wr.setnchannels(1)
            wr.setsampwidth(2)
            wr.setframerate(disclaimer_rate)

            for idx, chapter in enumerate(chapters, 1):
                # Guardrail at each chapter start.
                emit_disclaimer()

                # Spoken heading so the listener knows where they are.
                intro = CHAPTER_INTRO.format(n=idx)
                if (chapter.title or "").strip():
                    intro = f"{intro} {chapter.title.strip()}"
                emit(self.synth(intro, pacing), pacing.chapter_pause)

                body = (chapter.content or "").strip()
                if body:
                    paragraphs = _split_paragraphs(body)
                    for pi, para in enumerate(paragraphs):
                        if _is_scene_break(para):
                            if pi > 0:
                                wr.writeframes(
                                    _silence(disclaimer_rate, pacing.scene_pause)[0]
                                )
                                running_sec += pacing.scene_pause
                            continue
                        emit(self.synth(para, pacing), pacing.paragraph_pause)

                # Periodic re-guardrail if long enough since the last one.
                if running_sec - last_guard >= GUARDRAIL_INTERVAL_SEC:
                    emit_disclaimer()

        return {
            "chapters": len(chapters),
            "duration_seconds": running_sec,
            "disclaimers": disclaimer_count,
        }


def _wav_bytes_from_chunks(chunks: list) -> bytes:
    """Concatenate (pcm, rate) chunks into a WAV in memory (small clips only)."""
    if not chunks:
        return b""
    rate = chunks[0][1]
    frames = b"".join(pcm for pcm, _ in chunks)
    buf = tempfile.SpooledTemporaryFile(max_size=1_000_000)
    try:
        with wave.open(buf, "wb") as wr:
            wr.setnchannels(1)
            wr.setsampwidth(2)
            wr.setframerate(rate)
            wr.writeframes(frames)
        buf.seek(0)
        return buf.read()
    finally:
        buf.close()


_tts: TTSService | None = None


def get_tts() -> TTSService:
    global _tts
    if _tts is None:
        from app.config import get_settings

        model_dir = get_settings().data_dir / "tts"
        _tts = TTSService(model_dir)
    return _tts


if __name__ == "__main__":
    import argparse

    from app.config import get_settings

    parser = argparse.ArgumentParser(description="Download the piper TTS voice.")
    parser.add_argument(
        "action",
        nargs="?",
        default="download",
        choices=["download", "info"],
        help="download the voice model, or print model info",
    )
    args = parser.parse_args()

    svc = TTSService(get_settings().data_dir / "tts")
    if args.action == "download":
        if svc.available():
            print("Voice already present:", svc.model_path)
        else:
            import urllib.request

            base = (
                "https://huggingface.co/rhasspy/piper-voices/resolve/main/"
                f"en/en_US/lessac/medium/{VOICE_NAME}"
            )
            svc._model_dir.mkdir(parents=True, exist_ok=True)
            for suffix in (".onnx", ".onnx.json"):
                dest = svc._model_dir / f"{VOICE_NAME}{suffix}"
                url = base + suffix
                print(f"Downloading {url}")
                urllib.request.urlretrieve(url, dest)
                print("  ->", dest, dest.stat().st_size, "bytes")
    else:
        print("model:", svc.model_path, "exists:", svc.model_path.exists())
        print("config:", svc.config_path, "exists:", svc.config_path.exists())
