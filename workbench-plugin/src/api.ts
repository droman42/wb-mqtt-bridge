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

declare global {
  interface Window {
    /** Runtime API base injected by the embedding page, if any. */
    __LOCVEIL_BRIDGE_API__?: string;
  }
}

const STORAGE_KEY = 'locveil-bridge-api';
const DEFAULT_PORT = 8000;

/** Resolve the bridge controller base URL. Precedence: page-injected global →
 *  operator override (localStorage, settable from the voice-readiness page) →
 *  same-hostname fallback on the backend's standard port (covers a local dev
 *  backend; a workstation targeting the WB7 sets the override once). */
export function apiBase(): string {
  const injected = typeof window !== 'undefined' ? window.__LOCVEIL_BRIDGE_API__ : undefined;
  if (injected) return injected.replace(/\/+$/, '');
  const stored = typeof window !== 'undefined' ? window.localStorage.getItem(STORAGE_KEY) : null;
  if (stored) return stored.replace(/\/+$/, '');
  const hostname = typeof window !== 'undefined' ? window.location.hostname : 'localhost';
  return `http://${hostname}:${DEFAULT_PORT}`;
}

export function setApiBaseOverride(url: string | null): void {
  if (url && url.trim()) window.localStorage.setItem(STORAGE_KEY, url.trim());
  else window.localStorage.removeItem(STORAGE_KEY);
}

export function hasApiBaseOverride(): boolean {
  return window.localStorage.getItem(STORAGE_KEY) !== null;
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
