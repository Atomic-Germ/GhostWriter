"""TTS service + API tests. Uses a fake voice (no network, no real model)."""

import sys
import wave
from io import BytesIO
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("GW_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("GW_SKIP_EMBED_WARMUP", "1")

    from app.config import get_settings
    from app.db import storage as storage_mod
    from app.services import embeddings as emb_mod
    from app.services import indexer as indexer_mod
    from app.services import llm as llm_mod
    from app.services import rag as rag_mod

    get_settings.cache_clear()
    storage_mod._store = None
    llm_mod._llm = None
    rag_mod._memory = None
    indexer_mod._worker = None
    emb_mod._model = None
    emb_mod._load_error = "skipped in tests"
    emb_mod._status = "error"
    monkeypatch.setattr(emb_mod, "is_embedding_ready", lambda: False)
    monkeypatch.setattr(emb_mod, "warm_embeddings", lambda: False)

    class _FakeLLM:
        async def check_available(self, force=False):
            return False

        async def assist(self, **kwargs):
            return ("offline test reply", False)

        async def complete(self, **kwargs):
            return '{"characters": [], "world_facts": []}'

    monkeypatch.setattr(llm_mod, "get_llm", lambda: _FakeLLM())

    # Drop the piper voice model into the temp data dir so available() is True,
    # then fake the actual inference to keep tests hermetic and instant.
    tts_dir = tmp_path / "tts"
    tts_dir.mkdir(exist_ok=True)
    (tts_dir / "en_US-lessac-medium.onnx").write_bytes(b"fake-model")
    (tts_dir / "en_US-lessac-medium.onnx.json").write_text("{}", encoding="utf-8")

    from app.services import tts as tts_mod

    class _FakeVoice:
        def synthesize(self, text):
            # One chunk per text, ~100ms of silent 22050 Hz mono int16.
            samples = [0] * (2205)
            import struct

            pcm = struct.pack("<%dh" % len(samples), *samples)
            yield type(
                "Chunk",
                (),
                {"audio_int16_bytes": pcm, "sample_rate": 22050},
            )()

    class _FakeTTS(tts_mod.TTSService):
        def __init__(self, model_dir):
            super().__init__(model_dir)
            self._voice = _FakeVoice()

        def ensure_voice(self):
            return self._voice

    monkeypatch.setattr(tts_mod, "get_tts", lambda: _FakeTTS(tts_dir))

    from app.main import create_app

    app = create_app()
    with TestClient(app) as c:
        yield c

    get_settings.cache_clear()
    storage_mod._store = None


def _wav_ok(data: bytes) -> bool:
    try:
        with wave.open(BytesIO(data), "rb") as w:
            return w.getnchannels() == 1 and w.getframerate() == 22050
    except Exception:  # noqa: BLE001
        return False


def test_tts_status(client):
    p = client.post("/api/projects", json={"title": "Audio Book"}).json()
    r = client.get(f"/api/projects/{p['id']}/tts/status")
    assert r.status_code == 200
    body = r.json()
    assert body["available"] is True
    assert "not for publication" in body["guardrail"]
    assert body["guardrail_interval_seconds"] == 300


def test_tts_preview_returns_wav(client):
    p = client.post("/api/projects", json={"title": "Audio Book"}).json()
    r = client.post(
        f"/api/projects/{p['id']}/tts/preview",
        json={"text": "The cartographer traced the salt road."},
    )
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("audio/wav")
    assert _wav_ok(r.content)


def test_tts_preview_requires_text(client):
    p = client.post("/api/projects", json={"title": "Audio Book"}).json()
    r = client.post(f"/api/projects/{p['id']}/tts/preview", json={"text": "   "})
    assert r.status_code == 400


def test_tts_export_embeds_guardrails(client):
    p = client.post("/api/projects", json={"title": "Audio Book"}).json()
    client.post(
        f"/api/projects/{p['id']}/chapters",
        json={"title": "Chapter 1", "content": "Some prose to read."},
    )
    client.post(
        f"/api/projects/{p['id']}/chapters",
        json={"title": "Chapter 2", "content": "More prose to read aloud."},
    )
    r = client.get(f"/api/projects/{p['id']}/tts/export")
    assert r.status_code == 200
    assert _wav_ok(r.content)
    meta = r.headers.get("x-audio-meta", "")
    assert "chapters=2" in meta
    assert "disclaimers=2" in meta


def test_tts_export_requires_chapters(client):
    p = client.post("/api/projects", json={"title": "Empty"}).json()
    r = client.get(f"/api/projects/{p['id']}/tts/export")
    assert r.status_code == 400


def test_pacing_inserts_silence_between_paragraphs(tmp_path, monkeypatch):
    """Pauses between paragraphs/scenes add real silence to the WAV."""
    from app.services import tts as tts_mod

    tts_dir = tmp_path / "tts"
    tts_dir.mkdir(exist_ok=True)
    (tts_dir / "en_US-lessac-medium.onnx").write_bytes(b"fake-model")
    (tts_dir / "en_US-lessac-medium.onnx.json").write_text("{}", encoding="utf-8")

    import struct

    class _Voice:
        def synthesize(self, text):
            n = 2205  # 0.1s at 22050 Hz
            yield type(
                "Chunk",
                (),
                {
                    "audio_int16_bytes": struct.pack("<%dh" % n, *([0] * n)),
                    "sample_rate": 22050,
                },
            )()

    class _FakeTTS(tts_mod.TTSService):
        def __init__(self):
            super().__init__(tts_dir)
            self._voice = _Voice()

        def ensure_voice(self):
            return self._voice

    svc = _FakeTTS()
    text = "First paragraph.\n\nSecond paragraph.\n\n* * *\n\nThird paragraph."
    pacing = tts_mod.Pacing(
        paragraph_pause=0.5, scene_pause=1.5, chapter_pause=2.0, speech_rate=1.0
    )
    wav = svc.preview_wav(text, pacing)
    # 4 synth chunks * 0.1s = 0.4s + 2 paragraph pauses (0.5 each) + 1 scene
    # pause (1.5) = ~2.9s of audio.
    with wave.open(BytesIO(wav), "rb") as w:
        frames = w.getnframes()
        duration = frames / w.getframerate()
    assert duration > 2.0
    assert duration < 4.0

    # Default pacing is much lighter.
    wav_default = svc.preview_wav(text, tts_mod.Pacing())
    with wave.open(BytesIO(wav_default), "rb") as w:
        d0 = w.getnframes() / w.getframerate()
    assert d0 < duration


def test_pacing_rate_changes_synth_config_call(tmp_path, monkeypatch):
    """speech_rate != 1.0 passes a length-scaled synthesis config to piper."""
    from app.services import tts as tts_mod

    tts_dir = tmp_path / "tts"
    tts_dir.mkdir(exist_ok=True)
    (tts_dir / "en_US-lessac-medium.onnx").write_bytes(b"fake-model")
    (tts_dir / "en_US-lessac-medium.onnx.json").write_text("{}", encoding="utf-8")

    import struct

    calls = []

    class _Voice:
        def synthesize(self, text, syn_config=None):
            calls.append(syn_config)
            n = 2205
            yield type(
                "Chunk",
                (),
                {
                    "audio_int16_bytes": struct.pack("<%dh" % n, *([0] * n)),
                    "sample_rate": 22050,
                },
            )()

    class _FakeTTS(tts_mod.TTSService):
        def __init__(self):
            super().__init__(tts_dir)
            self._voice = _Voice()

        def ensure_voice(self):
            return self._voice

    svc = _FakeTTS()
    svc.preview_wav("Some words.", tts_mod.Pacing(speech_rate=1.2))
    assert len(calls) == 1 and calls[0] is not None
    assert abs(calls[0].length_scale - (1.0 / 1.2)) < 1e-6


def test_periodic_guardrail_reinserts_after_interval(tmp_path, monkeypatch):
    """A very long chapter triggers the ~5-min re-guardrail, not just the start."""
    from app.services import tts as tts_mod

    tts_dir = tmp_path / "tts"
    tts_dir.mkdir(exist_ok=True)
    (tts_dir / "en_US-lessac-medium.onnx").write_bytes(b"fake-model")
    (tts_dir / "en_US-lessac-medium.onnx.json").write_text("{}", encoding="utf-8")

    import struct

    class _LongVoice:
        def synthesize(self, text):
            # Emit 10s of silence per call regardless of text length.
            n = 22050 * 10
            yield type(
                "Chunk",
                (),
                {
                    "audio_int16_bytes": struct.pack("<%dh" % n, *([0] * n)),
                    "sample_rate": 22050,
                },
            )()

    class _FakeTTS(tts_mod.TTSService):
        def __init__(self):
            super().__init__(tts_dir)
            self._voice = _LongVoice()

        def ensure_voice(self):
            return self._voice

    svc = _FakeTTS()
    monkeypatch.setattr(tts_mod, "GUARDRAIL_INTERVAL_SEC", 25)  # tighten for test

    class Ch:
        def __init__(self, title, content):
            self.title = title
            self.content = content

    # 4 chapters x ~40s each (heading+body) = ~320s >> 25s interval
    chapters = [Ch("C%d" % i, "word " * 40) for i in range(4)]
    out = tmp_path / "book.wav"
    meta = svc.export_book(chapters, out)
    # Guardrail fires at every chapter start (4) plus multiple times mid-chapters.
    assert meta["disclaimers"] >= 4
    assert meta["duration_seconds"] > 100
    with wave.open(str(out), "rb") as w:
        assert w.getnframes() > 0

