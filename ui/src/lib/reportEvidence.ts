// Browser-side problem-report evidence (problem_reports_bridge.md B-4).
// Always-on, bounded, in-memory rings — dumped only into a report's ui_evidence
// payload when the user presses the navbar bug button. Nothing here leaves the
// browser on its own.

import { useLogStore } from '../stores/useLogStore';

const RING_MAX = 200;
const API_RING_MAX = 50;

interface ConsoleEntry {
  ts: number;
  level: 'error' | 'warn' | 'crash' | 'rejection';
  message: string;
}

interface ApiEntry {
  ts: number;
  method: string;
  path: string;
  status: number | null;
  durationMs: number;
  error?: string;
}

interface SseHealth {
  connected: boolean;
  lastEventTs?: number;
  lastErrorTs?: number;
}

const consoleRing: ConsoleEntry[] = [];
const apiRing: ApiEntry[] = [];
const sseHealth: Record<string, SseHealth> = {};

function push<T>(ring: T[], entry: T, max: number): void {
  ring.push(entry);
  if (ring.length > max) ring.splice(0, ring.length - max);
}

const fmt = (args: unknown[]): string =>
  args.map(a => {
    if (typeof a === 'string') return a;
    try { return JSON.stringify(a); } catch { return String(a); }
  }).join(' ').slice(0, 500);

/** Install the console/crash taps once, at app start (idempotent). */
let installed = false;
export function installEvidenceTaps(): void {
  if (installed) return;
  installed = true;
  const origError = console.error.bind(console);
  const origWarn = console.warn.bind(console);
  console.error = (...args: unknown[]) => {
    push(consoleRing, { ts: Date.now(), level: 'error', message: fmt(args) }, RING_MAX);
    origError(...args);
  };
  console.warn = (...args: unknown[]) => {
    push(consoleRing, { ts: Date.now(), level: 'warn', message: fmt(args) }, RING_MAX);
    origWarn(...args);
  };
  window.addEventListener('error', (e) => {
    push(consoleRing, { ts: Date.now(), level: 'crash', message: `${e.message} @ ${e.filename}:${e.lineno}` }, RING_MAX);
  });
  window.addEventListener('unhandledrejection', (e) => {
    push(consoleRing, { ts: Date.now(), level: 'rejection', message: fmt([e.reason]) }, RING_MAX);
  });
}

/** Fed by the axios interceptors in useApi. */
export function recordApiCall(entry: ApiEntry): void {
  push(apiRing, entry, API_RING_MAX);
}

/** Fed by useEventSource on open/error/message. */
export function reportSseState(url: string, patch: Partial<SseHealth>): void {
  const prev: SseHealth = sseHealth[url] ?? { connected: false };
  sseHealth[url] = { ...prev, ...patch };
}

/** The B-4 ui_evidence payload for POST /reports. */
export function collectUiEvidence(): Record<string, unknown> {
  return {
    app: {
      route: window.location.pathname,
      userAgent: navigator.userAgent,
      viewport: `${window.innerWidth}x${window.innerHeight}`,
      language: navigator.language,
      collectedAt: new Date().toISOString(),
    },
    // VWB-30 (#16): useLogStore unshifts new entries (newest at index 0), so slice(0, N)
    // takes the most recent N — the bug-relevant ones. slice(-N) took the OLDEST N.
    actionLog: useLogStore.getState().entries.slice(0, RING_MAX),
    console: [...consoleRing],
    apiCalls: [...apiRing],
    sse: { ...sseHealth },
  };
}
