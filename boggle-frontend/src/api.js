// All backend calls live here. Paths match starter_project_5 (Django REST API).
const BASE = "/api";
let token = localStorage.getItem("token");

export function setToken(t) {
  token = t;
  t ? localStorage.setItem("token", t) : localStorage.removeItem("token");
}

function message(data) {
  if (!data) return "Request failed";
  if (data.detail) return data.detail;
  const first = Object.values(data)[0];
  return Array.isArray(first) ? first[0] : String(first);
}

async function req(path, { method = "GET", body } = {}) {
  const res = await fetch(BASE + path, {
    method,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Token ${token}` } : {}),
    },
    body: body ? JSON.stringify(body) : undefined,
  });
  const data = res.status === 204 ? null : await res.json().catch(() => null);
  if (!res.ok) throw Object.assign(new Error(message(data)), { status: res.status });
  return data;
}

export const api = {
  games: () => req("/games/"),
  dictionaries: () => req("/dictionaries/"),
  createGame: (size, dictionary) =>
    req(`/game/${size}/`, { method: "POST", body: { dictionary } }),
  register: (username, password) =>
    req("/auth/register/", { method: "POST", body: { username, password } }),
  login: (username, password) =>
    req("/auth/token/", { method: "POST", body: { username, password } }),
  logout: () => req("/auth/logout/", { method: "POST" }),
  // authenticated session flow
  join: (gameId) => req(`/games/${gameId}/join/`, { method: "POST" }),
  start: (pid) => req(`/sessions/${pid}/start/`, { method: "POST" }),
  submit: (pid, word) => req(`/sessions/${pid}/words/`, { method: "POST", body: { word } }),
  finish: (pid) => req(`/sessions/${pid}/finish/`, { method: "POST" }),
  // guest-friendly endpoints (see BACKEND_PATCH.md)
  check: (gameId, word) => req(`/games/${gameId}/check/`, { method: "POST", body: { word } }),
  reveal: (gameId, found) => req(`/games/${gameId}/reveal/`, { method: "POST", body: { found } }),
};
