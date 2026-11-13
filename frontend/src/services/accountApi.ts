import { supabase } from "./cloudSession";
export class ApiFailure extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}
const base = (import.meta.env.VITE_REST_API_URL || "").replace(/\/$/, "");
async function accountRequest(
  path: string,
  init: RequestInit = {},
  expectedUser?: string,
) {
  if (!base || !supabase) throw new Error("Account service is not configured.");
  const { data, error } = await supabase.auth.getSession();
  if (
    error ||
    !data.session ||
    (expectedUser && data.session.user.id !== expectedUser)
  )
    throw new Error("Your account changed. Please try again.");
  const headers = new Headers(init.headers);
  headers.set("Authorization", `Bearer ${data.session.access_token}`);
  if (init.body && typeof init.body === "string")
    headers.set("Content-Type", "application/json");
  const response = await fetch(base + path, {
    ...init,
    signal: init.signal || AbortSignal.timeout(25000),
    headers,
    cache: "no-store",
  });
  if (!response.ok) {
    const value = await response.json().catch(() => null);
    throw new ApiFailure(
      response.status,
      value?.error?.message || "Could not save account data.",
    );
  }
  return response;
}
export async function accountApi(
  path: string,
  init: RequestInit = {},
  expectedUser?: string,
) {
  const response = await accountRequest(path, init, expectedUser);
  return response.status === 204 ? null : response.json();
}
export async function accountPhoto(
  id: string,
  signal: AbortSignal,
  user: string,
) {
  const response = await accountRequest(
    `/v1/progress/photos/${encodeURIComponent(id)}/image`,
    { signal },
    user,
  );
  return response.blob();
}

export async function publicApi(path: string, signal?: AbortSignal) {
  const response = await fetch(`${base || "/rest-api"}${path}`, {
    signal,
    cache: "no-store",
  });
  if (!response.ok) throw new Error("The product service is unavailable.");
  return response.json();
}
