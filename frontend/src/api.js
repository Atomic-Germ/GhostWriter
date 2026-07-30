const BASE = "/api";

async function request(path, options = {}) {
  const { timeoutMs, ...fetchOpts } = options;
  const controller = new AbortController();
  const ms = timeoutMs ?? 30_000;
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
        `Request timed out after ${Math.round(ms / 1000)}s. Backend may be stuck — restart \`python run.py\`.`
      );
    }
    if (err?.message === "Failed to fetch" || err?.name === "TypeError") {
      throw new Error("Cannot reach API. Is the backend running on :8000?");
    }
    throw err;
  } finally {
    clearTimeout(timer);
  }
}

/**
 * Stream assist via SSE. callbacks: onMeta, onToken, onDone, onError
 */
async function assistStream(body, { onMeta, onToken, onDone, onError, signal } = {}) {
  const res = await fetch(`${BASE}/assist/stream`, {
    method: "POST",
    headers: { "Content-Type": "application/json", Accept: "text/event-stream" },
    body: JSON.stringify(body),
    signal,
  });

  if (!res.ok) {
    const text = await res.text();
    let detail = text;
    try {
      detail = JSON.parse(text)?.detail || text;
    } catch {
      /* ignore */
    }
    throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
  }

  if (!res.body) {
    throw new Error("No response body for stream");
  }

  const reader = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let full = "";

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });

    // SSE events separated by blank line
    const parts = buffer.split("\n\n");
    buffer = parts.pop() || "";

    for (const part of parts) {
      const lines = part.split("\n");
      for (const line of lines) {
        if (!line.startsWith("data:")) continue;
        const raw = line.slice(5).trim();
        if (!raw || raw === "[DONE]") continue;
        let evt;
        try {
          evt = JSON.parse(raw);
        } catch {
          continue;
        }
        if (evt.type === "meta") {
          onMeta?.(evt);
        } else if (evt.type === "token") {
          full += evt.text || "";
          onToken?.(evt.text || "", full);
        } else if (evt.type === "error") {
          onError?.(evt.message || "Stream error");
        } else if (evt.type === "done") {
          onDone?.(full, evt);
        }
      }
    }
  }

  // If stream ended without explicit done
  if (full) onDone?.(full, {});
  return full;
}

export const api = {
  health: () => request("/health", { timeoutMs: 5_000 }),

  listProjects: () => request("/projects", { timeoutMs: 10_000 }),
  getProject: (id) => request(`/projects/${id}`, { timeoutMs: 10_000 }),
  createProject: (body) =>
    request("/projects", {
      method: "POST",
      body: JSON.stringify(body),
      timeoutMs: 10_000,
    }),
  updateProject: (id, body) =>
    request(`/projects/${id}`, {
      method: "PATCH",
      body: JSON.stringify(body),
      timeoutMs: 10_000,
    }),
  deleteProject: (id) =>
    request(`/projects/${id}`, { method: "DELETE", timeoutMs: 10_000 }),
  updateWorldNotes: (id, world_notes) =>
    request(`/projects/${id}/world-notes`, {
      method: "PUT",
      body: JSON.stringify({ world_notes }),
      timeoutMs: 15_000,
    }),

  listCharacters: (projectId) =>
    request(`/projects/${projectId}/characters`, { timeoutMs: 10_000 }),
  createCharacter: (projectId, body) =>
    request(`/projects/${projectId}/characters`, {
      method: "POST",
      body: JSON.stringify(body),
      timeoutMs: 10_000,
    }),
  updateCharacter: (projectId, characterId, body) =>
    request(`/projects/${projectId}/characters/${characterId}`, {
      method: "PATCH",
      body: JSON.stringify(body),
      timeoutMs: 10_000,
    }),
  deleteCharacter: (projectId, characterId) =>
    request(`/projects/${projectId}/characters/${characterId}`, {
      method: "DELETE",
      timeoutMs: 10_000,
    }),

  listChapters: (projectId) =>
    request(`/projects/${projectId}/chapters`, { timeoutMs: 10_000 }),
  createChapter: (projectId, body) =>
    request(`/projects/${projectId}/chapters`, {
      method: "POST",
      body: JSON.stringify(body),
      timeoutMs: 10_000,
    }),
  updateChapter: (projectId, chapterId, body) =>
    request(`/projects/${projectId}/chapters/${chapterId}`, {
      method: "PATCH",
      body: JSON.stringify(body),
      timeoutMs: 12_000,
    }),
  deleteChapter: (projectId, chapterId) =>
    request(`/projects/${projectId}/chapters/${chapterId}`, {
      method: "DELETE",
      timeoutMs: 10_000,
    }),

  assist: (body) =>
    request("/assist", {
      method: "POST",
      body: JSON.stringify(body),
      timeoutMs: 600_000,
    }),
  assistStream,
  index: (projectId, chapterId = null) =>
    request("/index", {
      method: "POST",
      body: JSON.stringify({ project_id: projectId, chapter_id: chapterId }),
      timeoutMs: 15_000,
    }),
};
