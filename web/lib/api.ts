export async function apiFetch(endpoint: string, options: RequestInit = {}) {
  const getBaseUrl = () => {
    // If a specific API URL is provided in environment variables, use it.
    if (process.env.NEXT_PUBLIC_API_URL) {
      return process.env.NEXT_PUBLIC_API_URL;
    }

    // In the browser, dynamically construct the API URL from the current page's hostname.
    // This makes the app portable (works on localhost, IPs, domains).
    if (typeof window !== 'undefined') {
      return `${window.location.protocol}//${window.location.hostname}:8000/api/v1`;
    }

    // As a fallback for server-side rendering, default to localhost.
    return 'http://localhost:8000/api/v1';
  };

  const baseUrl = getBaseUrl();

  const token = typeof window !== "undefined" ? localStorage.getItem("token") : null

  const headers: HeadersInit = {
    ...(options.headers || {}),
  }

  if (token) {
    (headers as any)["Authorization"] = `Bearer ${token}`
  }

  const res = await fetch(`${baseUrl}${endpoint}`, {
    ...options,
    headers,
  })

  if (!res.ok) {
    const errorBody = await res.text();
    console.error("API Error Response:", errorBody);
    throw new Error(`API error: ${res.status}`)
  }

  // Handle cases where the response might be empty
  const text = await res.text();
  return text ? JSON.parse(text) : {};
}
