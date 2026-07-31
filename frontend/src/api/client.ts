const BASE_URL = import.meta.env.VITE_API_URL || "/api";

export class ApiError extends Error {
  constructor(
    public status: number,
    public statusText: string,
    public body?: unknown
  ) {
    super(`API Error ${status}: ${statusText}`);
    this.name = "ApiError";
  }
}

function getAuthToken(): string | null {
  return localStorage.getItem("access_token");
}

export async function apiFetch<T>(
  path: string,
  options: RequestInit = {}
): Promise<T> {
  const token = getAuthToken();
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string>),
  };

  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  const response = await fetch(`${BASE_URL}${path}`, {
    ...options,
    headers,
  });

  if (!response.ok) {
    // If unauthorized on a REST API call, try refresh before forcing re-login
    if (response.status === 401) {
      // Don't immediately redirect — let the caller handle it
      // Only force logout if this isn't a background/mutation call
      const isBackgroundCall = options.method === "POST" || options.method === "PUT" || options.method === "DELETE";
      if (!isBackgroundCall) {
        localStorage.removeItem("access_token");
        localStorage.removeItem("refresh_token");
        window.location.reload();
      }
    }
    let body: unknown;
    try {
      body = await response.json();
    } catch {
      // ignore parse errors
    }
    throw new ApiError(response.status, response.statusText, body);
  }

  if (response.status === 204) {
    return undefined as T;
  }

  // Parse JSON and convert string numbers to actual numbers
  const json = await response.json();
  return deepParseNumbers(json) as T;
}

/**
 * Recursively convert numeric strings to numbers in API responses.
 * The backend returns Decimal fields as strings (e.g., "1320.0").
 * Skips strings that look like UUIDs, dates, or tokens.
 */
function deepParseNumbers(obj: unknown): unknown {
  if (obj === null || obj === undefined) return obj;
  if (Array.isArray(obj)) return obj.map(deepParseNumbers);
  if (typeof obj === "object") {
    const result: Record<string, unknown> = {};
    for (const [key, value] of Object.entries(obj as Record<string, unknown>)) {
      result[key] = deepParseNumbers(value);
    }
    return result;
  }
  if (typeof obj === "string" && obj !== "") {
    // Match numeric strings: integers, decimals, negatives (any length)
    if (/^-?\d+(\.\d+)?$/.test(obj)) {
      return Number(obj);
    }
  }
  return obj;
}
