export class ApiError extends Error {
  constructor(message, status, code, details = {}) {
    super(message);
    this.status = status;
    this.code = code;
    this.details = details;
  }
}

// One refresh exchange per expired session, including concurrent requests.
export function createClient({
  base = "/api/v1",
  fetcher = (...args) => fetch(...args),
  storage,
  onSession = () => {},
} = {}) {
  let tokens = null;
  let refreshPromise = null;
  try {
    tokens = JSON.parse(storage?.getItem("biletflow-session") || "null");
  } catch {
    /* Storage is optional. */
  }
  function save(value) {
    tokens = value;
    try {
      if (value) storage?.setItem("biletflow-session", JSON.stringify(value));
      else storage?.removeItem("biletflow-session");
    } catch {
      /* Keep in-memory session. */
    }
    onSession();
  }
  async function send(
    path,
    {
      method = "GET",
      body,
      signal,
      auth = true,
      raw = false,
      retried = false,
    } = {},
  ) {
    const access = auth ? tokens?.access_token : null;
    const headers = { Accept: raw ? "*/*" : "application/json" };
    if (access) headers.Authorization = `Bearer ${access}`;
    const multipart =
      typeof FormData !== "undefined" && body instanceof FormData;
    if (body !== undefined && !multipart)
      headers["Content-Type"] = "application/json";
    const response = await fetcher(`${base}${path}`, {
      method,
      headers,
      signal,
      body:
        body === undefined
          ? undefined
          : multipart
            ? body
            : JSON.stringify(body),
    });
    if (response.status === 401 && auth && !retried && tokens?.refresh_token) {
      if (access === tokens.access_token) {
        if (!refreshPromise) {
          const refreshToken = tokens.refresh_token;
          refreshPromise = send("/auth/refresh", {
            method: "POST",
            auth: false,
            body: { refresh_token: refreshToken },
          })
            .then((result) => {
              if (tokens?.refresh_token === refreshToken) save(result);
            })
            .catch((error) => {
              if (
                tokens?.refresh_token === refreshToken &&
                [401, 403].includes(error.status)
              )
                save(null);
              throw error;
            })
            .finally(() => {
              refreshPromise = null;
            });
        }
        await refreshPromise;
      }
      if (tokens)
        return send(path, { method, body, signal, auth, raw, retried: true });
    }
    if (!response.ok) {
      const data = await response.json().catch(() => ({}));
      if (response.status === 401 && auth && tokens?.access_token === access)
        save(null);
      if (
        response.status === 403 &&
        auth &&
        data.error?.code === "ACCOUNT_SUSPENDED"
      )
        save(null);
      throw new ApiError(
        data.error?.message || `Request failed (${response.status})`,
        response.status,
        data.error?.code,
        data.error?.details,
      );
    }
    if (raw) return response;
    if ([202, 204].includes(response.status)) return null;
    return response.json();
  }
  return {
    request: send,
    hasSession: () => Boolean(tokens?.access_token),
    async login(email, password) {
      const result = await send("/auth/login", {
        method: "POST",
        auth: false,
        body: { email, password },
      });
      save(result);
      return result;
    },
    async logout() {
      const refresh_token = tokens?.refresh_token;
      save(null);
      if (refresh_token)
        await send("/auth/logout", {
          method: "POST",
          auth: false,
          body: { refresh_token },
        });
    },
    async all(path, signal) {
      const items = [];
      for (let offset = 0; ; offset += 100) {
        const page = await send(
          `${path}${path.includes("?") ? "&" : "?"}limit=100&offset=${offset}`,
          { signal },
        );
        if (
          !Array.isArray(page?.items) ||
          !Number.isInteger(page.total) ||
          page.total < 0
        )
          throw new Error("The server returned an invalid list.");
        items.push(...page.items);
        if (items.length >= page.total) return items;
        if (!page.items.length)
          throw new Error("The server returned an incomplete list.");
      }
    },
  };
}
let storage;
try {
  storage = globalThis.sessionStorage;
} catch {
  /* Optional. */
}
export const apiBase = (
  import.meta.env?.VITE_API_BASE_URL || "/api/v1"
).replace(/\/$/, "");
export const client = createClient({
  base: apiBase,
  storage,
  onSession: () => globalThis.dispatchEvent?.(new Event("biletflow-session")),
});
export const api = client.request;
export const all = client.all;
export const login = client.login;
export const logout = client.logout;
export function query(values) {
  return new URLSearchParams(
    Object.entries(values).filter(([, value]) => value !== "" && value != null),
  ).toString();
}
export function apiPath(url) {
  const parsed = new URL(
    url,
    new URL(apiBase, globalThis.location?.origin || "http://localhost"),
  );
  const base = new URL(
    apiBase,
    globalThis.location?.origin || "http://localhost",
  );
  if (
    parsed.origin !== base.origin ||
    !parsed.pathname.startsWith(`${base.pathname}/`)
  )
    throw new Error("Invalid download address.");
  return parsed.pathname.slice(base.pathname.length) + parsed.search;
}
export async function download(path, name) {
  const response = await api(path, { raw: true });
  const url = URL.createObjectURL(await response.blob());
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = name;
  anchor.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
