import axios from "axios";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
export const API = `${BACKEND_URL}/api`;

export const http = axios.create({ baseURL: API });

export const listSessions = () => http.get("/sessions").then((r) => r.data);
export const createSession = (payload) => http.post("/sessions", payload).then((r) => r.data);
export const getSession = (id) => http.get(`/sessions/${id}`).then((r) => r.data);
export const updateSession = (id, payload) => http.put(`/sessions/${id}`, payload).then((r) => r.data);
export const deleteSession = (id) => http.delete(`/sessions/${id}`).then((r) => r.data);
export const resetSession = (id) => http.post(`/sessions/${id}/reset`).then((r) => r.data);

export async function transcribe(blob) {
  const fd = new FormData();
  fd.append("file", blob, "audio.webm");
  fd.append("language", "fr");
  const r = await http.post("/transcribe", fd, { headers: { "Content-Type": "multipart/form-data" } });
  return r.data.text;
}

// Streams a turn. Calls onMeta/onDelta/onDone/onError. Returns an AbortController.
export function streamMessage(sessionId, body, handlers) {
  const controller = new AbortController();
  (async () => {
    try {
      const resp = await fetch(`${API}/sessions/${sessionId}/message`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
        signal: controller.signal,
      });
      const reader = resp.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const events = buffer.split("\n\n");
        buffer = events.pop();
        for (const chunk of events) {
          const lines = chunk.split("\n");
          let ev = "message";
          let data = "";
          for (const l of lines) {
            if (l.startsWith("event:")) ev = l.slice(6).trim();
            else if (l.startsWith("data:")) data += l.slice(5).trim();
          }
          if (!data) continue;
          const parsed = JSON.parse(data);
          if (ev === "meta") handlers.onMeta?.(parsed);
          else if (ev === "delta") handlers.onDelta?.(parsed.content);
          else if (ev === "done") handlers.onDone?.(parsed.content);
          else if (ev === "error") handlers.onError?.(parsed.detail);
        }
      }
      handlers.onClose?.();
    } catch (e) {
      if (e.name === "AbortError") handlers.onAbort?.();
      else handlers.onError?.(e.message);
    }
  })();
  return controller;
}
