// In produzione frontend e backend condividono la stessa origine: gli URL sono
// relativi (API_BASE = ""). In sviluppo il dev server Vite fa da proxy verso il
// backend (vedi vite.config.ts). Si può forzare un backend esterno con VITE_API_BASE_URL.
const API_BASE = import.meta.env.VITE_API_BASE_URL ?? "";

export const WS_BASE =
  import.meta.env.VITE_WS_BASE_URL ??
  (typeof window !== "undefined"
    ? `${window.location.protocol === "https:" ? "wss" : "ws"}://${window.location.host}`
    : "");

export class ApiError extends Error {
  code: string;
  status: number;
  details: Record<string, unknown>;

  constructor(message: string, code: string, status: number, details: Record<string, unknown>) {
    super(message);
    this.code = code;
    this.status = status;
    this.details = details;
  }
}

async function request<T>(method: string, path: string, body?: unknown): Promise<T> {
  const res = await fetch(API_BASE + path, {
    method,
    credentials: "include",
    headers: body !== undefined ? { "Content-Type": "application/json" } : {},
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });

  const text = await res.text();
  let parsed: any = null;
  try {
    parsed = text ? JSON.parse(text) : null;
  } catch {
    // risposta non-JSON (es. pagina d'errore del proxy): la trattiamo come ApiError
    parsed = null;
  }

  if (!res.ok || (text && parsed === null)) {
    const err = parsed?.error ?? {};
    throw new ApiError(
      err.message ?? `Errore di connessione (${res.status}). Riprova.`,
      err.code ?? "error.http",
      res.status,
      err.details ?? {},
    );
  }
  return parsed as T;
}

export const api = {
  base: API_BASE,
  get: <T>(path: string) => request<T>("GET", path),
  post: <T>(path: string, body?: unknown) => request<T>("POST", path, body),
  put: <T>(path: string, body?: unknown) => request<T>("PUT", path, body),
  del: <T>(path: string) => request<T>("DELETE", path),
};
