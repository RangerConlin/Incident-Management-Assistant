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

export const api = {
  download: (path: string, body: unknown) => request<DownloadResult>("POST", path, body, "download"),
  get: <T>(path: string) => request<T>("GET", path),
  post: <T>(path: string, body?: unknown) => request<T>("POST", path, body ?? {}),
  put: <T>(path: string, body?: unknown) => request<T>("PUT", path, body ?? {}),
  patch: <T>(path: string, body?: unknown) => request<T>("PATCH", path, body ?? {}),
  delete: <T>(path: string) => request<T>("DELETE", path),
};
