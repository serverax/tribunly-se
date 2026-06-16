/**
 * Auth helpers mirroring client/public/js/auth.js (httpOnly cookie model).
 * Uses Next.js rewrites so browser calls same-origin /api/auth/*.
 */

export type AuthUser = {
  id: string;
  email?: string;
  created_at?: string;
  subscription_status?: string;
};

const JSON_HEADERS = { "Content-Type": "application/json" };

export async function fetchWithAuth(
  url: string,
  options: RequestInit = {},
): Promise<Response> {
  const opts: RequestInit = {
    ...options,
    credentials: options.credentials ?? "include",
    headers: {
      ...JSON_HEADERS,
      ...(options.headers || {}),
    },
  };
  const res = await fetch(url, opts);
  if (res.status === 401 || res.status === 403) {
    throw new AuthError("Authentication required", res.status);
  }
  return res;
}

export class AuthError extends Error {
  constructor(
    message: string,
    public status: number,
  ) {
    super(message);
    this.name = "AuthError";
  }
}

export async function getCurrentUser(): Promise<AuthUser | null> {
  const res = await fetch("/api/auth/me", { credentials: "include" });
  if (res.status === 401 || res.status === 403) return null;
  if (!res.ok) throw new Error(`Auth check failed: ${res.status}`);
  return res.json();
}

export async function login(email: string, password: string): Promise<void> {
  const res = await fetch("/api/auth/login", {
    method: "POST",
    credentials: "include",
    headers: JSON_HEADERS,
    body: JSON.stringify({ email, password }),
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `Login failed: ${res.status}`);
  }
}

export async function logout(): Promise<void> {
  await fetch("/api/auth/logout", {
    method: "POST",
    credentials: "include",
    headers: JSON_HEADERS,
    body: JSON.stringify({ all_sessions: true }),
  });
}
