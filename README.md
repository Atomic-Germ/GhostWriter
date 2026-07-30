# GhostWriter

Intelligent writing companion for authors. GhostWriter keeps a living memory of your characters, chapters, and world lore, then uses RAG + an LLM to help you brainstorm, continue prose, check consistency, and catch plot holes.

## Features (MVP)

- **Distraction-free editor** — projects, chapters, autosave, word counts
- **Character dossiers** — traits, motivations, speech patterns, relationships
- **World & lore notes** — freeform world-building stored with the manuscript
- **Story memory (RAG)** — chapters/characters/world notes chunked into ChromaDB
- **AI assist modes** — Brainstorm · Continue · Consistency · Lore · Plot · Influence
- **Influence Analyzer** — maps literary/thematic resonances with cited evidence (craft awareness, not judgment)
- **Local-first LLM** — any OpenAI-compatible API (llama.cpp server, Ollama, OpenAI, …)
- **Offline fallbacks** — useful checklists when no model is running

## Stack

| Layer | Tech |
|--------|------|
| Frontend | React, Vite, Tailwind CSS |
| Backend | Python, FastAPI |
| Memory | ChromaDB + sentence-transformers |
| LLM | OpenAI-compatible HTTP API |

## Quick start

### 1. Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python run.py
```

API: http://127.0.0.1:8000  
Docs: http://127.0.0.1:8000/docs

Optional env (see `backend/.env.example`):

```bash
export GW_LLM_BASE_URL=http://localhost:11434/v1   # Ollama
export GW_LLM_MODEL=llama3.2
```

### 2. Frontend

```bash
cd frontend
npm install
npm run dev
```

App: http://127.0.0.1:5173

### 3. LLM (optional but recommended)

**llama.cpp server**

```bash
llama-server -m /path/to/model.gguf --port 8080
# default GW_LLM_BASE_URL=http://localhost:8080/v1
```

**Ollama**

```bash
ollama serve
ollama pull llama3.2
export GW_LLM_BASE_URL=http://localhost:11434/v1
export GW_LLM_MODEL=llama3.2
```

Without a model, the app still runs; assist endpoints return offline guidance.

## Project layout

```
GhostWriter/
├── backend/
│   ├── app/
│   │   ├── api/          # FastAPI routers
│   │   ├── db/           # JSON project storage
│   │   ├── models/       # Pydantic schemas
│   │   ├── services/     # RAG, embeddings, LLM
│   │   ├── config.py
│   │   └── main.py
│   ├── requirements.txt
│   └── run.py
├── frontend/
│   └── src/              # React UI
├── data/                 # projects + chroma (runtime)
└── tests/
```

## Tests

```bash
cd backend && source .venv/bin/activate
pip install pytest httpx
cd ..
pytest tests/ -q
```

## How assist works

1. You write chapters and fill character/world panels.
2. Content is chunked and embedded into a per-project Chroma collection.
3. On assist, GhostWriter retrieves relevant story fragments + full character dossiers.
4. Context is sent to the LLM with a mode-specific system prompt.
5. Sources used for retrieval are shown in the AI panel.

## Roadmap

- **Phase 2** — deeper plot-hole detection, automated consistency scoring, subplot tracker
- **Phase 3** — collaboration, export (DOCX/EPUB), richer world graph

## License

MIT
