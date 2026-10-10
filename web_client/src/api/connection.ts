// Where this client reaches its server. Default ("internal") is no override
// at all: every request stays same-origin/relative, i.e. whatever server is
// already serving this page — the normal case for a LAN server, an offline
// server, or a cloud server reached directly. Setting a domain switches to
// building absolute URLs through cloud_router's public connect-code path
// (https://<domain>/r/<code>/...) instead, for when this app is opened from
// somewhere that isn't already the right server (a bookmark, a cold start)
// — see Design Documents/Instructions/cloud_router_architecture.md.

const DOMAIN_KEY = "sarapp.connection.domain";
const CODE_KEY = "sarapp.connection.code";

export function getDomain(): string | null {
  try {
    return localStorage.getItem(DOMAIN_KEY) || null;
  } catch {
    return null;
  }
}

export function setDomain(domain: string | null): void {
  try {
    const trimmed = domain?.trim();
    if (trimmed) localStorage.setItem(DOMAIN_KEY, trimmed);
    else localStorage.removeItem(DOMAIN_KEY);
  } catch {
    // best-effort only
  }
}

export function getConnectCode(): string | null {
  try {
    return localStorage.getItem(CODE_KEY) || null;
  } catch {
    return null;
  }
}

export function setConnectCode(code: string | null): void {
  try {
    const trimmed = code?.trim();
    if (trimmed) localStorage.setItem(CODE_KEY, trimmed);
    else localStorage.removeItem(CODE_KEY);
  } catch {
    // best-effort only
  }
}

/** True when a domain override is configured (i.e. not using same-origin/"internal"). */
export function hasConnectionOverride(): boolean {
  return Boolean(getDomain());
}

function normalizeDomain(domain: string): string {
  const withScheme = /^https?:\/\//i.test(domain) ? domain : `https://${domain}`;
  return withScheme.replace(/\/$/, "");
}

/** Prefix to put in front of every API/WS path. Empty string = same-origin default. */
export function getUrlPrefix(): string {
  const domain = getDomain();
  if (!domain) return "";
  const code = getConnectCode();
  return `${normalizeDomain(domain)}${code ? `/r/${encodeURIComponent(code)}` : ""}`;
}

/** Builds a full request URL for a root-relative API path like "/api/...". */
export function buildUrl(path: string): string {
  return `${getUrlPrefix()}${path}`;
}

/** Builds a ws:// or wss:// URL for a root-relative path like "/api/incidents/{id}/ws". */
export function buildWsUrl(path: string): string {
  const prefix = getUrlPrefix();
  if (!prefix) {
    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    return `${protocol}//${window.location.host}${path}`;
  }
  return `${prefix.replace(/^http/, "ws")}${path}`;
}
