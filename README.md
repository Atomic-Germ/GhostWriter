# GhostWriter *Just a Helpful Ghost*
## It won't write for you though.

Intelligent writing companion for authors. GhostWriter's AI is Arthur, and Arthur is never the author. Arthur does not try to be the author. It reads what you write and keeps story bible of your characters, chapters, and world lore, then uses RAG with an LLM of your choice to help you brainstorm, check consistency of characters and world-building over stories and entire series, and catch plot holes. Most features don't actually require a running LLM -- because *Arthur isn't the Author*.

## Features (MVP)

- **Distraction-free editor** — projects, chapters, autosave, word counts

- **Character dossiers** — traits, motivations, speech patterns, relationships
  <img width="2880" height="1920" alt="Screenshot From 2026-08-08 09-05-24" src="https://github.com/user-attachments/assets/d813879b-27df-4190-83d7-d91b0e4e690e" />
  <img width="2880" height="1920" alt="Screenshot From 2026-08-08 09-05-24" src="https://github.com/user-attachments/assets/027d4a1e-1097-490d-83eb-f37ade900216" />
  
- **World & lore notes** — freeform world-building stored with the manuscript
  <img width="2880" height="1920" alt="Screenshot From 2026-08-08 09-05-36" src="https://github.com/user-attachments/assets/ec579824-cf6a-4780-99f3-4bfd779bc28b" />
  <img width="2880" height="1920" alt="Screenshot From 2026-08-08 09-06-04" src="https://github.com/user-attachments/assets/8bdf0d6e-7eef-4970-9b08-f057b8f0fae1" />

- **Story memory (RAG)** — chapters/characters/world notes chunked into ChromaDB
  
- **Influence Analyzer** — maps literary/thematic resonances with cited evidence (craft awareness, not judgment)
  <img width="2880" height="1920" alt="Screenshot From 2026-08-08 09-09-36" src="https://github.com/user-attachments/assets/53b4ea96-66f7-4503-9333-1a09237db99d" />
  
- **Story map** — tension pulse, chapter mass, cast presence grid, arc lanes, story circle, co-presence links -- This is the most useful feature for most authors. It offloads mental overhead that isn't the storyline.
  <img width="2880" height="1920" alt="Screenshot From 2026-08-08 09-04-50" src="https://github.com/user-attachments/assets/6d54ba0b-259a-474f-93c6-13c39c4e3f6c" />
  <img width="2880" height="1920" alt="Screenshot From 2026-08-08 09-05-05" src="https://github.com/user-attachments/assets/7f180329-3970-4053-b816-c35b0b871f6d" />

- **Export** — Markdown, plain text, HTML, DOCX, EPUB, no-publish watermarked WAV, or full JSON backup
  
- **Local-first LLM** — any OpenAI-compatible API (llama.cpp server, Ollama, OpenAI, FastFlowLM, etc)
  
- **LLM Not Required** — useful checklists and most mapping features work fine when no model is running

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

**FastFlowLM** (Recommended for AMD AI 340+ machines, light. Any Atomic-Germ or FastFlowLM HuggingFace or Modelscope repo will work, results vary)

```bash
wget https://huggingface.co/Atomic-Germ/Qwen3.5-9B-Claude-4.8-Opus-NPU2/resolve/main/flm-add.py
python3 ./flm-add.py Atomic-Germ/Qwen3.5-9B-Claude-4.8-Opus-NPU2 
FLM_CONFIG_PATH="$HOME/.config/flm/model_list.json" FLM_XCLBIN_PATH="$HOME/.config/flm" flm serve qwen3.5-claude:9b --port 8080
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
