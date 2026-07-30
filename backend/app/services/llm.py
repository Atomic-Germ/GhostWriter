"""LLM client for OpenAI-compatible APIs (llama.cpp server, Ollama, OpenAI)."""

from __future__ import annotations

import logging
import time
from typing import Optional

import httpx

from app.config import get_settings

logger = logging.getLogger("ghostwriter.llm")

MODE_SYSTEM_PROMPTS = {
    "brainstorm": (
        "You are GhostWriter, a creative writing partner for novelists. "
        "Help brainstorm plot twists, scene ideas, character motivations, and dialogue. "
        "Stay consistent with the provided story context. Be specific and actionable. "
        "Do not rewrite the entire chapter unless asked — offer focused suggestions."
    ),
    "continue": (
        "You are GhostWriter, a skilled ghostwriter. Continue the prose in the author's "
        "voice and style. Match tone, tense, and POV from the context. "
        "Write 1–3 polished paragraphs that advance the scene naturally. "
        "Do not add meta commentary — only the continued prose."
    ),
    "consistency": (
        "You are GhostWriter, a story continuity editor. Analyze the provided text "
        "against character profiles and story memory. Flag contradictions in "
        "personality, appearance, knowledge, relationships, timeline, or world rules. "
        "If nothing is wrong, say so. Structure findings as a short bullet list."
    ),
    "lore": (
        "You are GhostWriter, a world-building archivist. Answer questions using the "
        "story's established lore, world notes, and characters. Infer carefully from "
        "what is written; label speculation clearly. If something is unknown, say so."
    ),
    "plot": (
        "You are GhostWriter, a narrative structure analyst. Evaluate plot threads, "
        "pacing, unresolved hooks, and arc structure. Identify potential plot holes "
        "and suggest how to resolve or deepen them. Be constructive and concrete."
    ),
}


class LLMService:
    def __init__(self):
        self.settings = get_settings()
        self._available: Optional[bool] = None
        self._available_checked_at: float = 0.0
        self._resolved_model: Optional[str] = None

    @property
    def base_url(self) -> str:
        return self.settings.llm_base_url.rstrip("/")

    def _headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self.settings.llm_api_key}",
            "Content-Type": "application/json",
        }

    async def check_available(self, force: bool = False) -> bool:
        # Cache for 30s so assist doesn't add extra latency every call
        now = time.monotonic()
        if (
            not force
            and self._available is not None
            and now - self._available_checked_at < 30
        ):
            return self._available

        try:
            async with httpx.AsyncClient(timeout=3.0) as client:
                r = await client.get(
                    f"{self.base_url}/models",
                    headers=self._headers(),
                )
                if r.status_code < 500:
                    self._available = True
                    self._available_checked_at = now
                    # Prefer configured model; else first model from server
                    try:
                        data = r.json()
                        models = [
                            m.get("id")
                            for m in data.get("data", [])
                            if m.get("id")
                        ]
                        cfg = self.settings.llm_model
                        if cfg and cfg != "local-model" and (
                            not models or cfg in models
                        ):
                            self._resolved_model = cfg
                        elif models:
                            self._resolved_model = models[0]
                        else:
                            self._resolved_model = cfg or "local-model"
                        logger.info(
                            "LLM available at %s model=%s",
                            self.base_url,
                            self._resolved_model,
                        )
                    except Exception:  # noqa: BLE001
                        self._resolved_model = self.settings.llm_model
                    return True
        except Exception as exc:  # noqa: BLE001
            logger.warning("LLM health check failed: %s", exc)

        self._available = False
        self._available_checked_at = now
        return False

    def _model_name(self) -> str:
        return self._resolved_model or self.settings.llm_model or "local-model"

    async def complete(
        self,
        *,
        user_message: str,
        system_prompt: str,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ) -> str:
        # Cap tokens to keep local gen responsive; user can raise via env
        max_tok = (
            max_tokens
            if max_tokens is not None
            else min(self.settings.llm_max_tokens, 2048)
        )
        payload = {
            "model": self._model_name(),
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            "temperature": temperature
            if temperature is not None
            else self.settings.llm_temperature,
            "max_tokens": max_tok,
            "stream": False,
        }
        url = f"{self.base_url}/chat/completions"
        logger.info(
            "POST %s model=%s max_tokens=%s prompt_chars=%s",
            url,
            payload["model"],
            max_tok,
            len(user_message),
        )
        timeout = httpx.Timeout(connect=10.0, read=300.0, write=30.0, pool=10.0)
        async with httpx.AsyncClient(timeout=timeout) as client:
            r = await client.post(url, headers=self._headers(), json=payload)
            if r.status_code >= 400:
                logger.error("LLM error %s: %s", r.status_code, r.text[:500])
                r.raise_for_status()
            data = r.json()
            content = data["choices"][0]["message"]["content"]
            # Some models wrap thinking in tags — strip empty
            text = (content or "").strip()
            logger.info("LLM response chars=%s", len(text))
            return text

    async def assist(
        self,
        *,
        mode: str,
        prompt: str,
        context: str,
        context_text: str = "",
    ) -> tuple[str, bool]:
        """Returns (response_text, llm_available)."""
        available = await self.check_available()
        system = MODE_SYSTEM_PROMPTS.get(mode, MODE_SYSTEM_PROMPTS["brainstorm"])

        user_parts = [
            "### Story Context\n" + (context or "(no story context yet)"),
        ]
        if context_text.strip():
            user_parts.append("### Current Draft Excerpt\n" + context_text.strip())
        user_parts.append("### Request\n" + prompt.strip())
        user_message = "\n\n".join(user_parts)

        if not available:
            logger.info("Assist offline fallback mode=%s", mode)
            return self._offline_response(mode, prompt, context, context_text), False

        try:
            text = await self.complete(
                user_message=user_message,
                system_prompt=system,
            )
            if not text:
                return (
                    "The model returned an empty response. Check llama.cpp logs "
                    f"and model id (`{self._model_name()}`).",
                    True,
                )
            return text, True
        except Exception as exc:  # noqa: BLE001
            logger.exception("LLM assist failed")
            fallback = self._offline_response(mode, prompt, context, context_text)
            return (
                f"{fallback}\n\n_(LLM call failed: {exc})_",
                False,
            )

    def _offline_response(
        self,
        mode: str,
        prompt: str,
        context: str,
        context_text: str,
    ) -> str:
        char_hint = ""
        if "Character:" in context:
            names = [
                line.replace("Character:", "").strip()
                for line in context.splitlines()
                if line.startswith("Character:")
            ]
            if names:
                char_hint = ", ".join(names[:8])

        if mode == "continue":
            excerpt = (context_text or "").strip()
            tail = excerpt[-280:] if excerpt else ""
            return (
                "**Offline mode** — no LLM is connected.\n\n"
                "Start a local model server to enable prose continuation, e.g.:\n"
                "```\n"
                "llama-server -m models/your-model.gguf --port 8080\n"
                "# or: ollama serve  (then set GW_LLM_BASE_URL=http://localhost:11434/v1)\n"
                "```\n\n"
                + (f"Last draft snippet for reference:\n> …{tail}" if tail else "")
            )

        if mode == "consistency":
            return (
                "**Offline consistency checklist**\n\n"
                f"- Characters on file: {char_hint or 'none yet — add dossiers first'}\n"
                "- Check dialogue against speech patterns in each profile.\n"
                "- Verify physical descriptions match established traits.\n"
                "- Ensure characters don't know facts they shouldn't yet.\n"
                "- Cross-check locations/items against world notes.\n\n"
                "Connect an LLM for automated contradiction detection."
            )

        if mode == "plot":
            return (
                "**Offline plot review scaffold**\n\n"
                "1. List active subplots and their last on-page beat.\n"
                "2. Mark any setup without payoff (and vice versa).\n"
                "3. Note timeline jumps that need bridges.\n"
                "4. Check whether the protagonist's goal is still clear this chapter.\n\n"
                f"Your question: {prompt}\n\n"
                "Connect an LLM for full narrative arc analysis."
            )

        if mode == "lore":
            return (
                "**Offline lore lookup**\n\n"
                "I can't query the model right now, but your world notes "
                "and character dossiers are in context when the LLM is connected.\n\n"
                f"Query: {prompt}\n"
                f"Known characters: {char_hint or 'none'}\n"
            )

        return (
            "**Offline brainstorm**\n\n"
            f"Prompt: {prompt}\n\n"
            "Ideas to explore manually while LLM is offline:\n"
            "- Raise stakes by tying the obstacle to a character motivation.\n"
            "- Add a ticking clock or competing goal in this scene.\n"
            "- Reveal one secret through subtext rather than exposition.\n"
            f"- Lean on established cast: {char_hint or 'add characters for richer prompts'}.\n\n"
            "Start llama.cpp or Ollama and retry for full AI assistance.\n"
            f"Expected endpoint: `{self.base_url}/chat/completions`"
        )


_llm: Optional[LLMService] = None


def get_llm() -> LLMService:
    global _llm
    if _llm is None:
        _llm = LLMService()
    return _llm
