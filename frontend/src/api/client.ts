const base = (
  import.meta.env.VITE_API_BASE_URL || "http://localhost:8000"
).replace(/\/$/, "");

export async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 30000);
  try {
    const response = await fetch(`${base}/api${path}`, {
      ...init,
      signal: controller.signal,
    });
    if (!response.ok) {
      const messages: Record<number, string> = {
        400: "Please check the question or entity ID.",
        404: "No matching entity was retrieved.",
        503: "A backend dependency is unavailable. Please retry.",
      };
      throw new Error(
        messages[response.status] ||
          `Request failed (${response.status}). Please retry.`,
      );
    }
    return (await response.json()) as T;
  } catch (error) {
    if (
      error instanceof TypeError ||
      (error instanceof DOMException && error.name === "AbortError")
    ) {
      throw new Error(
        "Cannot reach the API or the request timed out. Please retry.",
      );
    }
    throw error;
  } finally {
    clearTimeout(timer);
  }
}
