// Tiny wrapper around localStorage for the handful of per-browser
// preferences the UI needs (API base URL override, API key, whether to
// save analyses to server-side history by default). Every read/write is
// wrapped in try/catch: localStorage can throw in private browsing modes
// or when third-party storage is blocked, and losing a preference should
// never break the app.

const KEYS = {
  apiKey: "pgpa.apiKey",
  saveByDefault: "pgpa.saveByDefault",
};

function safeGet(key, fallback) {
  try {
    const value = window.localStorage.getItem(key);
    return value === null ? fallback : value;
  } catch (_e) {
    return fallback;
  }
}

function safeSet(key, value) {
  try {
    window.localStorage.setItem(key, value);
  } catch (_e) {
    // ignore - preference just won't persist this session
  }
}

export function getApiKey() {
  return safeGet(KEYS.apiKey, "");
}

export function setApiKey(value) {
  safeSet(KEYS.apiKey, value || "");
}

export function getSaveByDefault() {
  return safeGet(KEYS.saveByDefault, "false") === "true";
}

export function setSaveByDefault(value) {
  safeSet(KEYS.saveByDefault, value ? "true" : "false");
}
