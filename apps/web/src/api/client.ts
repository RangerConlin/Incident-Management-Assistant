import { buildUrl } from "./connection";

const TOKEN_KEY = "sarapp.token";

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string | null): void {
  if (token) localStorage.setItem(TOKEN_KEY, token);
  else localStorage.removeItem(TOKEN_KEY);
}

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function request<T>(method: string, path: string, body?: unknown, responseType: "json" | "download" = "json"): Promise<T> {
  const headers: Record<string, string> = {};
  const token = getToken();
  if (token) headers["Authorization"] = `Bearer ${token}`;
  if (body !== undefined) headers["Content-Type"] = "application/json";

  const res = await fetch(buildUrl(path), {
    method,
    headers,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });

  if (!res.ok) {
    let detail = res.statusText;
    try {
      const data = await res.json();
      detail = data.detail || detail;
    } catch {
      // response had no JSON body; fall back to statusText
    }
    throw new ApiError(res.status, detail);
  }
  if (res.status === 204) return undefined as T;
  if (responseType === "download") {
    if (!res.headers.get("Content-Type")?.includes("application/pdf")) throw new ApiError(res.status, "The server did not return a PDF.");
    const disposition = res.headers.get("Content-Disposition") || "";
    const rawName = disposition.match(/filename="([^"\r\n]+)"/i)?.[1] || "form.pdf";
    const filename = rawName.replace(/[^A-Za-z0-9_.-]/g, "_");
    return { blob: await res.blob(), filename } as T;
  }
  return (await res.json()) as T;
}

export interface DownloadResult { blob: Blob; filename: string; }

// Generic attachment upload (multipart/form-data) — used by the attachments
// router's owner_type/owner_id pattern (server/sarapp_db/.../routers/
// attachments.py), not form-specific like `download` above. No
// Content-Type header: the browser sets its own multipart boundary for a
// FormData body, and setting one manually breaks that.
async function requestUpload<T>(path: string, formData: FormData): Promise<T> {
  const headers: Record<string, string> = {};
  const token = getToken();
  if (token) headers["Authorization"] = `Bearer ${token}`;
  const res = await fetch(buildUrl(path), { method: "POST", headers, body: formData });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const data = await res.json();
      detail = data.detail || detail;
    } catch {
      // response had no JSON body; fall back to statusText
    }
    throw new ApiError(res.status, detail);
  }
  return (await res.json()) as T;
}

// Generic file download — any mime type, filename parsed from the
// attachments router's RFC 5987 `filename*=UTF-8''...` header (not the
// plain `filename="..."` the PDF-only `download` path above expects).
async function requestFile(path: string): Promise<DownloadResult> {
  const headers: Record<string, string> = {};
  const token = getToken();
  if (token) headers["Authorization"] = `Bearer ${token}`;
  const res = await fetch(buildUrl(path), { method: "GET", headers });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const data = await res.json();
      detail = data.detail || detail;
    } catch {
      // response had no JSON body; fall back to statusText
    }
    throw new ApiError(res.status, detail);
  }
  const disposition = res.headers.get("Content-Disposition") || "";
  const rawName =
    disposition.match(/filename\*=UTF-8''([^;\r\n]+)/i)?.[1] ?? disposition.match(/filename="?([^"\r\n;]+)"?/i)?.[1] ?? "attachment";
  const filename = decodeURIComponent(rawName);
  return { blob: await res.blob(), filename };
}

export const api = {
  download: (path: string, body: unknown) => request<DownloadResult>("POST", path, body, "download"),
  uploadFile: <T>(path: string, formData: FormData) => requestUpload<T>(path, formData),
  fetchFile: (path: string) => requestFile(path),
  get: <T>(path: string) => request<T>("GET", path),
  post: <T>(path: string, body?: unknown) => request<T>("POST", path, body ?? {}),
  put: <T>(path: string, body?: unknown) => request<T>("PUT", path, body ?? {}),
  patch: <T>(path: string, body?: unknown) => request<T>("PATCH", path, body ?? {}),
  delete: <T>(path: string) => request<T>("DELETE", path),
};
