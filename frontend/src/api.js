const API_BASE = "http://127.0.0.1:8000";

async function apiGet(path) {
  const res = await fetch(`${API_BASE}${path}`);
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

async function apiPost(path, body = null) {
  const opts = { method: "POST" };
  if (body !== null) {
    opts.headers = { "Content-Type": "application/json" };
    opts.body = JSON.stringify(body);
  }
  const res = await fetch(`${API_BASE}${path}`, opts);
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

async function apiUpload(path, file) {
  const formData = new FormData();
  formData.append("file", file);
  const res = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    body: formData,
  });
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

const api = {
  health: () => apiGet("/api/health"),
  config: () => apiGet("/api/config"),
  currentMeeting: () => apiGet("/api/calendar/current-meeting"),
  upcomingMeetings: () => apiGet("/api/calendar/upcoming"),
  startRecording: (body) => apiPost("/api/recording/start", body),
  stopRecording: () => apiPost("/api/recording/stop"),
  recordingStatus: () => apiGet("/api/recording/status"),
  listNotes: () => apiGet("/api/notes/list"),

  // Saved recordings (failed processing)
  savedRecordings: () => apiGet("/api/recording/saved"),
  retrySavedRecording: (id) => apiPost(`/api/recording/retry/${id}`),

  // Settings
  getSettings: () => apiGet("/api/settings"),
  updateSettings: (data) => apiPost("/api/settings", data),
  uploadCredentials: (file) => apiUpload("/api/settings/credentials", file),
  setupStatus: () => apiGet("/api/settings/setup-status"),
};
