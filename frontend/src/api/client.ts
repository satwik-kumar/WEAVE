const BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000';

export async function apiGet<T>(path: string): Promise<T> {
  const url = path.startsWith('http')
    ? path
    : `${BASE_URL}${path.startsWith('/') ? path : `/${path}`}`;
  const response = await fetch(url);
  if (!response.ok) {
    let message = `HTTP ${response.status} ${response.statusText}`;
    try {
      const err = await response.json();
      if (err?.detail) {
        message = typeof err.detail === 'string' ? err.detail : JSON.stringify(err.detail);
      }
    } catch {
      // ignore non-json error responses
    }
    throw new Error(message);
  }
  return response.json() as Promise<T>;
}

export async function apiPost<T, B = unknown>(path: string, body: B): Promise<T> {
  const url = path.startsWith('http')
    ? path
    : `${BASE_URL}${path.startsWith('/') ? path : `/${path}`}`;
  const response = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!response.ok) {
    let message = `HTTP ${response.status} ${response.statusText}`;
    try {
      const err = await response.json();
      if (err?.detail) {
        message = typeof err.detail === 'string' ? err.detail : JSON.stringify(err.detail);
      }
    } catch {
      // ignore non-json error responses
    }
    throw new Error(message);
  }
  return response.json() as Promise<T>;
}
