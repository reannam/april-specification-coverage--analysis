const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

export const getDownloadUrl = (url?: string | null) => {
  if (!url) return "";
  if (/^https?:\/\//.test(url)) return url;
  const normalised = url.trim().replace(/^\.\/+/, "/").replace(/^backend\/outputs/i, "/outputs").replace(/^\/backend\/outputs/i, "/outputs");
  return `${API_BASE_URL}${normalised.startsWith("/") ? normalised : `/${normalised}`}`;
};

const readError = async (response: Response) => {
  const text = await response.text();
  try {
    const parsed = JSON.parse(text);
    return parsed.detail ?? parsed.message ?? text;
  } catch {
    return text || "The request could not be completed.";
  }
};

export async function postFormData<T>(endpoint: string, formData: FormData): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${endpoint}`, { method: "POST", body: formData });
  if (!response.ok) throw new Error(await readError(response));
  return response.json() as Promise<T>;
}

export async function fetchJson<T>(url?: string | null): Promise<T> {
  if (!url) throw new Error("No file URL was provided.");
  const response = await fetch(getDownloadUrl(url));
  if (!response.ok) throw new Error(await readError(response));
  return response.json() as Promise<T>;
}
