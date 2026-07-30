const BASE = "/api";

async function request(path, options = {}) {
  const { timeoutMs, ...fetchOpts } = options;
  const controller = new AbortController();
  const ms = timeoutMs ?? 60_000;
  const timer = setTimeout(() => controller.abort(), ms);

  try {
    const res = await fetch(`${BASE}${path}`, {
      headers: {
        "Content-Type": "application/json",
        ...(fetchOpts.headers || {}),
      },
      ...fetchOpts,
      signal: controller.signal,
    });
    if (res.status === 204) return null;
    const text = await res.text();
    let data = null;
    try {
      data = text ? JSON.parse(text) : null;
    } catch {
      data = text;
    }
    if (!res.ok) {
      const detail = data?.detail || data || res.statusText;
      throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
    }
    return data;
  } catch (err) {
    if (err?.name === "AbortError") {
      throw new Error(
        `Request timed out after ${Math.round(ms / 1000)}s. Is the backend running, and is the model responding?`
      );
    }
    if (err?.message === "Failed to fetch" || err?.name === "TypeError") {
      throw new Error(
        "Cannot reach API (proxy/backend). Check that `python run.py` is up on :8000."
      );
    }
    throw err;
  } finally {
    clearTimeout(timer);
  }
}

export const api = {
  health: () => request("/health", { timeoutMs: 8_000 }),

  listProjects: () => request("/projects"),
  getProject: (id) => request(`/projects/${id}`),
  createProject: (body) =>
    request("/projects", { method: "POST", body: JSON.stringify(body) }),
  updateProject: (id, body) =>
    request(`/projects/${id}`, { method: "PATCH", body: JSON.stringify(body) }),
  deleteProject: (id) => request(`/projects/${id}`, { method: "DELETE" }),
  updateWorldNotes: (id, world_notes) =>
    request(`/projects/${id}/world-notes`, {
      method: "PUT",
      body: JSON.stringify({ world_notes }),
    }),

  listCharacters: (projectId) => request(`/projects/${projectId}/characters`),
  createCharacter: (projectId, body) =>
    request(`/projects/${projectId}/characters`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  updateCharacter: (projectId, characterId, body) =>
    request(`/projects/${projectId}/characters/${characterId}`, {
      method: "PATCH",
      body: JSON.stringify(body),
    }),
  deleteCharacter: (projectId, characterId) =>
    request(`/projects/${projectId}/characters/${characterId}`, {
      method: "DELETE",
    }),

  listChapters: (projectId) => request(`/projects/${projectId}/chapters`),
  createChapter: (projectId, body) =>
    request(`/projects/${projectId}/chapters`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  updateChapter: (projectId, chapterId, body) =>
    request(`/projects/${projectId}/chapters/${chapterId}`, {
      method: "PATCH",
      body: JSON.stringify(body),
    }),
  deleteChapter: (projectId, chapterId) =>
    request(`/projects/${projectId}/chapters/${chapterId}`, {
      method: "DELETE",
    }),

  // Local models can take a while; keep this generous
  assist: (body) =>
    request("/assist", {
      method: "POST",
      body: JSON.stringify(body),
      timeoutMs: 300_000,
    }),
  index: (projectId, chapterId = null) =>
    request("/index", {
      method: "POST",
      body: JSON.stringify({ project_id: projectId, chapter_id: chapterId }),
      timeoutMs: 15_000,
    }),
};
