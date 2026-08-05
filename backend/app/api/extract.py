import asyncio
import json
import logging
import re

from fastapi import APIRouter, HTTPException

from app.db.storage import get_store
from app.models.schemas import ExtractRequest, ExtractResponse, ExtractedCharacter
from app.services.llm import MODE_SYSTEM_PROMPTS, get_llm
from app.services.rag import StoryMemory

logger = logging.getLogger("ghostwriter.extract")

router = APIRouter(prefix="/projects", tags=["extract"])

_JSON_FENCE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL | re.IGNORECASE)

# Used when a thinking model burned its output budget on a reasoning preamble
# and never emitted the JSON. Short, insistent, and schema-first.
_RETRY_SYSTEM_PROMPT = (
    "You are GhostWriter's universe extractor. Your previous attempt returned no "
    "valid JSON. Now output ONLY a JSON object with exactly two keys describing the "
    "cast and setting established in the prose below.\n\n"
    'Schema: {"characters": [{"name": "...", "role": "...", "physical_traits": "...", '
    '"personality": "...", "motivations": "...", "speech_patterns": "...", '
    '"backstory": "...", "relationships": "...", "notes": "..."}], '
    '"world_facts": ["...", "..."]}\n\n'
    "Include every named character, especially newly introduced ones, using their "
    "exact full name from the prose. Do not reason, plan, or narrate — emit the JSON "
    "immediately and nothing else."
)


def _char_from_dict(item) -> ExtractedCharacter | None:
    """Map a raw character dict to a schema object (skips non-characters)."""
    if not isinstance(item, dict) or not item.get("name"):
        return None
    return ExtractedCharacter(
        name=str(item.get("name", "")).strip()[:200],
        role=str(item.get("role", "") or "").strip()[:200],
        physical_traits=str(item.get("physical_traits", "") or "").strip()[:500],
        personality=str(item.get("personality", "") or "").strip()[:1000],
        motivations=str(item.get("motivations", "") or "").strip()[:1000],
        speech_patterns=str(item.get("speech_patterns", "") or "").strip()[:500],
        backstory=str(item.get("backstory", "") or "").strip()[:2000],
        relationships=str(item.get("relationships", "") or "").strip()[:1000],
        notes=str(item.get("notes", "") or "").strip()[:1000],
    )


def _balanced_objects(text: str) -> list[dict]:
    """Yield every brace-balanced JSON object in text that parses on its own.

    Thinking models sometimes close the array before emitting every object
    (e.g. `[ {…}], {…}], {…}], "world_facts": …`). This rescues each object
    individually instead of failing on the malformed whole.
    """
    objs: list[dict] = []
    i = 0
    n = len(text)
    while True:
        i = text.find("{", i)
        if i == -1 or len(objs) > 200:
            break
        j = i
        depth = 0
        in_str = False
        esc = False
        while j < n:
            ch = text[j]
            if in_str:
                if esc:
                    esc = False
                elif ch == "\\":
                    esc = True
                elif ch == '"':
                    in_str = False
            elif ch == '"':
                in_str = True
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    j += 1
                    break
            j += 1
        if depth == 0 and j > i:
            raw = text[i:j]
            i = j
            try:
                obj = json.loads(raw)
            except json.JSONDecodeError:
                continue
            if isinstance(obj, dict):
                objs.append(obj)
        else:
            i += 1
    return objs


def _string_values(text: str) -> list[str]:
    """Collect decoded string literals in order, skipping JSON keys."""
    out: list[str] = []
    i = 0
    n = len(text)
    while True:
        i = text.find('"', i)
        if i == -1:
            break
        j = i + 1
        buf: list[str] = []
        esc = False
        while j < n:
            ch = text[j]
            if esc:
                if ch == '"':
                    buf.append('"')
                elif ch == "\\":
                    buf.append("\\")
                else:
                    buf.append(ch)
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                break
            else:
                buf.append(ch)
            j += 1
        if j >= n:
            break
        value = "".join(buf)
        k = j + 1
        while k < n and text[k] in " \t\r\n":
            k += 1
        if k < n and text[k] != ":":
            out.append(value)
        i = j + 1
    return out


def _fact_overlaps(a: str, b: str) -> bool:
    """True if two facts are near-duplicates (exact, substring, or word overlap)."""
    la, lb = a.lower(), b.lower()
    if la == lb:
        return True
    if len(la) > 4 and la in lb:
        return True
    if len(lb) > 4 and lb in la:
        return True
    wa, wb = set(la.split()), set(lb.split())
    if not wa or not wb:
        return False
    inter = len(wa & wb)
    return inter >= 0.7 * min(len(wa), len(wb))


def _clean_world_facts(facts: list[str]) -> list[str]:
    """Drop fragments and near-duplicate facts (thinking models ramble)."""
    out: list[str] = []
    for f in facts:
        s = re.sub(r"\s+", " ", (f or "").strip())
        if len(s) < 5 or len(s.split()) < 2:
            continue
        if any(_fact_overlaps(s, a) for a in out):
            continue
        out.append(s[:500])
    return out


def _repair_extraction(text: str) -> ExtractResponse | None:
    """Best-effort recovery from malformed model output (see _balanced_objects)."""
    ckey = text.find('"characters"')
    wkey = text.find('"world_facts"')
    region_end = wkey if wkey != -1 else len(text)

    characters: list[ExtractedCharacter] = []
    seen: set[str] = set()
    if ckey != -1:
        for obj in _balanced_objects(text[ckey + 1 : region_end]):
            c = _char_from_dict(obj)
            if c and c.name.lower() not in seen:
                seen.add(c.name.lower())
                characters.append(c)

    world_facts: list[str] = []
    if wkey != -1:
        world_facts = _clean_world_facts(
            s.strip() for s in _string_values(text[wkey:]) if s.strip()
        )

    if characters or world_facts:
        return ExtractResponse(
            characters=characters,
            world_facts=world_facts,
            raw=text,
        )
    return None


def _parse_extraction(raw: str) -> ExtractResponse:
    """Parse model output into a structured response; best-effort fallbacks."""
    text = (raw or "").strip()
    if not text:
        return ExtractResponse(raw=raw)

    # Strip markdown fences if present, otherwise use the raw text
    fence = _JSON_FENCE.search(text)
    candidate = fence.group(1).strip() if fence else text
    # Find the outermost JSON object
    start = candidate.find("{")
    end = candidate.rfind("}")
    if start != -1 and end > start:
        try:
            data = json.loads(candidate[start : end + 1])
            if isinstance(data, dict):
                characters = [
                    c for c in (_char_from_dict(i) for i in data.get("characters") or []) if c
                ]
                world_facts = _clean_world_facts(
                    f for f in data.get("world_facts") or [] if isinstance(f, str)
                )
                return ExtractResponse(
                    characters=characters,
                    world_facts=world_facts,
                    raw=raw,
                )
        except json.JSONDecodeError:
            pass

    repaired = _repair_extraction(text)
    if repaired is not None:
        logger.info("Extraction: strict JSON parse failed — repaired output")
        return repaired

    return ExtractResponse(raw=raw)


@router.post("/{project_id}/extract", response_model=ExtractResponse)
async def extract_from_story(project_id: str, payload: ExtractRequest):
    """Read prose and return proposed characters + world facts (no plot)."""
    store = get_store()
    llm = get_llm()

    try:
        project = await asyncio.to_thread(store.get_project, project_id)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e

    chapters = sorted(project.chapters, key=lambda c: c.order)
    if payload.chapter_id:
        chapters = [c for c in chapters if c.id == payload.chapter_id]
    if not chapters:
        return ExtractResponse(raw="No chapter content to extract from.")

    bodies = [(ch.content or "").strip() for ch in chapters]
    bodies = [b for b in bodies if b]
    if not bodies:
        return ExtractResponse(raw="No chapter content to extract from.")

    # Whole-book extraction must not drop the tail — new cast usually appears in
    # later chapters, and front-filling the budget silently ignores them. Give
    # every chapter a fair share, keeping each chapter's head and tail.
    budget = 60000
    if sum(len(b) for b in bodies) <= budget:
        prose_parts = bodies
    else:
        per = max(80, budget // len(bodies))
        prose_parts = [StoryMemory._clip_chapter_body(b, per) for b in bodies]

    user_message = (
        "Extract the cast and worldbuilding from this story prose (ignore plot):\n\n"
        + "\n\n".join(prose_parts)
    )

    available = await llm.check_available()
    if not available:
        raise HTTPException(
            status_code=503,
            detail="No LLM connected — start llama.cpp to extract from the story.",
        )

    async def _run(system_prompt: str, max_tokens: int) -> str:
        try:
            return await llm.complete(
                user_message=user_message,
                system_prompt=system_prompt,
                temperature=0.2,
                max_tokens=max_tokens,
            )
        except Exception as exc:  # noqa: BLE001
            logger.exception("Extract LLM call failed")
            raise HTTPException(status_code=502, detail=f"Extraction failed: {exc}") from exc

    raw = await _run(MODE_SYSTEM_PROMPTS["extract"], 16384)
    result = _parse_extraction(raw)

    if not result.characters and not result.world_facts and (raw or "").strip():
        # Thinking models often spend their whole output budget on a reasoning
        # preamble and never write the JSON. Give them one tight second chance.
        logger.info("Extraction: empty parse — retrying with strict JSON prompt")
        retried = await _run(_RETRY_SYSTEM_PROMPT, 8192)
        reparsed = _parse_extraction(retried)
        if reparsed.characters or reparsed.world_facts:
            result = reparsed
        else:
            result = ExtractResponse(raw=retried or raw)

    logger.info(
        "Extract done project=%s characters=%s facts=%s",
        project_id,
        len(result.characters),
        len(result.world_facts),
    )
    return result
