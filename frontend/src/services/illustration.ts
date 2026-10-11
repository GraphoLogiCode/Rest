import { accessToken, cloudEnabled } from './cloudSession';
export type Box = [number, number, number, number];
export type IllustrationJob = { progress?: number; progressStage?: string; id: string; status: 'queued' | 'running' | 'completed' | 'failed'; imageUrl?: string; error?: string };
const endpoint = '/illustration-api';
const cloudBase = (import.meta.env.VITE_REST_API_URL || '').replace(/\/$/, '');
const imageCache = new Map<string, string>();
export { cloudEnabled };
export function releaseIllustrationImage(id: string) {
  const url = imageCache.get(id);
  if (url) URL.revokeObjectURL(url);
  imageCache.delete(id);
}
async function cloudFetch(path: string, init: RequestInit = {}) {
  const token = await accessToken();
  return fetch(`${cloudBase}${path}`, { ...init, headers: { ...init.headers, Authorization: `Bearer ${token}` } });
}
function requestKey() {
  const bytes = crypto.getRandomValues(new Uint8Array(16));
  bytes[6] = (bytes[6] & 15) | 64; bytes[8] = (bytes[8] & 63) | 128;
  const hex = Array.from(bytes, b => b.toString(16).padStart(2, '0')).join('');
  return `${hex.slice(0,8)}-${hex.slice(8,12)}-${hex.slice(12,16)}-${hex.slice(16,20)}-${hex.slice(20)}`;
}
async function cloudJob(response: Response, signal: AbortSignal): Promise<IllustrationJob> {
  const value = await (await checked(response)).json();
  if (!value || typeof value.id !== 'string' || !/^[0-9a-f-]{36}$/.test(value.id) || !['queued','running','completed','failed'].includes(value.status)) throw new Error('Unexpected preview response.');
  if (value.status === 'completed') {
    let url = imageCache.get(value.id);
    if (!url) {
      // Derive the authenticated path; do not send bearer tokens to a returned URL.
      const result = await checked(await cloudFetch(`/v1/jobs/${value.id}/image`, { signal }));
      if (!result.headers.get('content-type')?.startsWith('image/png')) throw new Error('Invalid preview image.');
      const blob = await result.blob();
      signal.throwIfAborted();
      url = URL.createObjectURL(blob);
      imageCache.set(value.id, url);
    }
    value.imageUrl = url;
  }
  return value;
}
async function checked(response: Response) {
  if (!response.ok) {
    const detail = await response.json().catch(() => ({}));
    throw new Error(typeof detail.error?.message === 'string' ? detail.error.message : typeof detail.detail === 'string' ? detail.detail : cloudEnabled ? 'Cloud preview is unavailable. Please try again.' : 'Start the local face-preview service, then try again.');
  }
  return response;
}
async function job(response: Response): Promise<IllustrationJob> {
  const value = await (await checked(response)).json();
  if (!value || typeof value.id !== 'string' || !['queued','running','completed','failed'].includes(value.status)) throw new Error('Unexpected preview response.');
  if (value.status === 'completed') {
    if (typeof value.imageUrl !== 'string') throw new Error('Preview image is missing.');
    const url = new URL(value.imageUrl, new URL(`${endpoint}/`, location.origin));
    if (url.origin !== location.origin || !url.pathname.startsWith(`${endpoint}/jobs/`)) throw new Error('Invalid preview image address.');
    value.imageUrl = url.href;
  }
  return value;
}
export async function createIllustration(reference: File, options: {faceBox: Box; editBox: Box; strength: string; finish: string; product: string}, signal: AbortSignal) {
  if (cloudEnabled) {
    // This function is called only after the photo-specific consent checkbox.
    await checked(await cloudFetch('/v1/consents/illustration', { method: 'PUT', signal,
      headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ version: 'illustration-2026-10-11' }) }));
    const body = new FormData();
    body.append('reference', reference); body.append('consent', 'true');
    body.append('options', JSON.stringify({ mode: 'face-edit', face_box: options.faceBox, edit_box: options.editBox,
      strength: Number(options.strength), finish: options.finish }));
    return cloudJob(await cloudFetch('/v1/illustrations', { method: 'POST', body, signal,
      headers: { 'Idempotency-Key': requestKey() } }), signal);
  }
  await checked(await fetch(`${endpoint}/session`, {method:'POST', signal}));
  const body = new FormData();
  body.append('reference', reference);
  body.append('consent', 'true');
  body.append('face_box', JSON.stringify(options.faceBox));
  body.append('edit_box', JSON.stringify(options.editBox));
  for (const key of ['strength', 'finish', 'product'] as const) body.append(key, options[key]);
  return job(await fetch(`${endpoint}/jobs`, {method:'POST', body, signal}));
}
export async function getIllustration(id: string, signal: AbortSignal) {
  if (cloudEnabled) return cloudJob(await cloudFetch(`/v1/jobs/${encodeURIComponent(id)}`, { signal }), signal);
  return job(await fetch(`${endpoint}/jobs/${encodeURIComponent(id)}`, {signal}));
}
export async function deleteIllustration(id: string) {
  releaseIllustrationImage(id);
  if (cloudEnabled) {
    const response = await cloudFetch(`/v1/jobs/${encodeURIComponent(id)}`, { method: 'DELETE', keepalive: true });
    if (response.status !== 404) await checked(response);
    return;
  }
  const response = await fetch(`${endpoint}/jobs/${encodeURIComponent(id)}`, {method:'DELETE', keepalive:true});
  if (response.status !== 404) await checked(response);
}
