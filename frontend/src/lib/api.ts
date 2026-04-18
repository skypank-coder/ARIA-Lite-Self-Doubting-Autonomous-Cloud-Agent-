/**
 * API Configuration for ARIA-Lite Frontend
 * Supports both local (Vite proxy) and production (Render backend) modes
 */

const API_BASE_URL = import.meta.env.VITE_API_URL || "/api";

export function getApiUrl(endpoint: string): string {
  // Remove leading slash if present
  const normalizedPath = endpoint.startsWith("/") ? endpoint.slice(1) : endpoint;
  
  // In production, use full URL; in dev, use relative path with /api prefix
  if (import.meta.env.PROD) {
    return `${API_BASE_URL}/${normalizedPath}`;
  }
  
  return `/api/${normalizedPath}`;
}

export async function apiCall<T>(
  endpoint: string,
  options: RequestInit = {}
): Promise<T> {
  const url = getApiUrl(endpoint);
  
  const response = await fetch(url, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...options.headers,
    },
  });

  if (!response.ok) {
    throw new Error(`API Error: ${response.status} ${response.statusText}`);
  }

  return response.json();
}
