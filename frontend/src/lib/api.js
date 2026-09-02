import { getApiKey } from "./settings";

const API_BASE = (import.meta.env.VITE_API_URL || "http://localhost:8000").replace(/\/+$/, "");
const V1 = `${API_BASE}/api/v1`;

export class ApiError extends Error {
  constructor(message, status, body) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.body = body;
  }
}

function authHeaders() {
  const key = getApiKey();
  return key ? { "X-API-Key": key } : {};
}

async function request(path, { method = "GET", body, headers = {} } = {}) {
  let res;
  try {
    res = await fetch(path, {
      method,
      headers: {
        ...(body ? { "Content-Type": "application/json" } : {}),
        ...authHeaders(),
        ...headers,
      },
      body: body ? JSON.stringify(body) : undefined,
    });
  } catch (networkError) {
    throw new ApiError(
      `Could not reach the pgPlanAdvisor API at ${API_BASE}. Is the backend running? (${networkError.message})`,
      0,
      null
    );
  }

  if (!res.ok) {
    let detail = res.statusText;
    try {
      const data = await res.json();
      detail = data.detail || JSON.stringify(data);
    } catch (_e) {
      try {
        detail = await res.text();
      } catch (_e2) {
        /* keep statusText */
      }
    }
    throw new ApiError(detail || `Request failed with status ${res.status}`, res.status, detail);
  }
  return res;
}

function coercePlan(planText) {
  try {
    return JSON.parse(planText);
  } catch (_e) {
    return planText;
  }
}

export async function analyzePlan(planText, query, { save = false, label = null } = {}) {
  const res = await request(`${V1}/analyze`, {
    method: "POST",
    body: { plan: coercePlan(planText), query, save, label },
  });
  return res.json();
}

export async function exportMarkdown(planText, query) {
  const res = await request(`${V1}/analyze/export`, {
    method: "POST",
    body: { plan: coercePlan(planText), query },
  });
  return res.text();
}

export async function fetchHistory({ limit = 50, offset = 0 } = {}) {
  const res = await request(`${V1}/history?limit=${limit}&offset=${offset}`);
  return res.json();
}

export async function fetchHistoryItem(id) {
  const res = await request(`${V1}/history/${encodeURIComponent(id)}`);
  return res.json();
}

export async function deleteHistoryItem(id) {
  await request(`${V1}/history/${encodeURIComponent(id)}`, { method: "DELETE" });
}

export async function exportHistoryItem(id) {
  const res = await request(`${V1}/history/${encodeURIComponent(id)}/export`);
  return res.text();
}

export function downloadTextFile(filename, content, mime = "text/markdown") {
  const blob = new Blob([content], { type: mime });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
}
