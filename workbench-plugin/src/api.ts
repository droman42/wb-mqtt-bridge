/* The bridge controller API client — typed against the embedded generated types
   (own gen:api-types; the shell never sees a schema — cross-repo-source-of-truth).
   One backend target class for all pages: the FastAPI backend on the controller
   (workbench_split.md §2.2). */

import type { components } from '@/types/openapi.gen';

export type SystemInfo = components['schemas']['SystemInfo'];
export type CatalogResponse = components['schemas']['CatalogResponse'];
export type CatalogDevice = components['schemas']['CatalogDevice'];
export type CatalogCapability = components['schemas']['CatalogCapability'];
export type CatalogAction = components['schemas']['CatalogAction'];
export type BaseDeviceConfig = components['schemas']['BaseDeviceConfig'];
export type RoomDefinitionResponse = components['schemas']['RoomDefinitionResponse'];
export type CanonicalActionRequest = components['schemas']['CanonicalActionRequest'];
export type ReportRequest = components['schemas']['ReportRequest'];

const STORAGE_KEY = 'locveil-bridge-api';
const DEFAULT_PORT = 8000;

let shellBase: string | null = null;

/** Fed from `PageProps.backends.api` by the page wrapper (IMPL-6): deployment facts
 *  live in the owner-edited shell config, never in build artifacts. Relative fetches
 *  would resolve against the SHELL origin — always go through apiBase(). */
export function setShellBase(url: string | undefined): void {
  shellBase = url ? url.replace(/\/+$/, '') : null;
}

/** Resolve the bridge controller base URL. Precedence: operator override
 *  (localStorage — the user-level escape hatch, settable from the voice-readiness
 *  page) → the shell-configured backend (IMPL-6) → same-hostname fallback on the
 *  backend's standard port (covers only a shell with no backends configured). */
export function apiBase(): string {
  const stored = typeof window !== 'undefined' ? window.localStorage.getItem(STORAGE_KEY) : null;
  if (stored) return stored.replace(/\/+$/, '');
  if (shellBase) return shellBase;
  const hostname = typeof window !== 'undefined' ? window.location.hostname : 'localhost';
  return `http://${hostname}:${DEFAULT_PORT}`;
}

export function setApiBaseOverride(url: string | null): void {
  if (url && url.trim()) window.localStorage.setItem(STORAGE_KEY, url.trim());
  else window.localStorage.removeItem(STORAGE_KEY);
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${apiBase()}${path}`, {
    headers: { 'Content-Type': 'application/json', ...(init?.headers ?? {}) },
    ...init,
  });
  if (!res.ok) {
    let detail = `${res.status} ${res.statusText}`;
    try {
      const body = await res.json();
      if (body && typeof body === 'object' && 'detail' in body) {
        detail = `${res.status}: ${JSON.stringify((body as { detail: unknown }).detail)}`;
      }
    } catch {
      /* non-JSON error body — keep the status line */
    }
    throw new Error(detail);
  }
  return res.json() as Promise<T>;
}

export const api = {
  getSystem: () => request<SystemInfo>('/system'),
  getCatalog: () => request<CatalogResponse>('/system/catalog'),
  getDeviceConfigs: () => request<Record<string, BaseDeviceConfig>>('/config/devices'),
  listRooms: () => request<RoomDefinitionResponse[]>('/room/list'),
  canonical: (deviceId: string, body: CanonicalActionRequest) =>
    request<Record<string, unknown>>(`/devices/${encodeURIComponent(deviceId)}/canonical`, {
      method: 'POST',
      body: JSON.stringify(body),
    }),
  report: (body: ReportRequest) =>
    request<Record<string, unknown>>('/reports', { method: 'POST', body: JSON.stringify(body) }),
};
