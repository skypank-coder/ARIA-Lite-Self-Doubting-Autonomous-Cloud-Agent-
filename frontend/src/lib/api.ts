/**
 * API Client for ARIA-Lite++
 * Automatically handles both local (Vite proxy) and production (direct URL) environments
 */

export function getApiUrl(): string {
  // In development, use empty string (Vite proxy handles /api routing)
  if (!import.meta.env.PROD) {
    return "";
  }
  
  // In production, use VITE_API_URL or fallback
  const apiUrl = import.meta.env.VITE_API_URL;
  if (!apiUrl) {
    console.warn("VITE_API_URL not set. API calls may fail in production.");
    return "";
  }
  
  // Remove trailing slash if present
  return apiUrl.endsWith("/") ? apiUrl.slice(0, -1) : apiUrl;
}

export async function apiCall<T>(
  endpoint: string,
  options?: RequestInit
): Promise<T> {
  const apiUrl = getApiUrl();
  const baseUrl = import.meta.env.PROD ? apiUrl : "";
  const url = `${baseUrl}/api${endpoint}`;

  const response = await fetch(url, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...options?.headers,
    },
  });

  if (!response.ok) {
    const error = await response.text();
    throw new Error(`API Error (${response.status}): ${error}`);
  }

  return response.json() as Promise<T>;
}

export async function processTicket(ticket: string) {
  return apiCall("/process_ticket", {
    method: "POST",
    body: JSON.stringify({ ticket }),
  });
}

export async function explainTrust(ticket: string) {
  return apiCall("/trust/explain", {
    method: "POST",
    body: JSON.stringify({ ticket }),
  });
}

export async function getHealth() {
  return apiCall("/health");
}

export async function getMemory() {
  return apiCall("/memory");
}

export async function getAuditLog() {
  return apiCall("/audit");
}
