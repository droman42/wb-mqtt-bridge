// SCN-11: per-device force-reconcile dialog — the scenario-level escape hatch for
// optimistic-state desync. Lists every device the ACTIVE scenario involves with the
// bridge's believed state vs the scenario's desired state. NB the inversion: an
// "in sync" row is exactly where force matters — "in sync" only means the BELIEF
// matches; the user standing in the room is the feedback channel saying it doesn't.
// Tap a row → it expands to the derived chain + worst-case ETA (fat-finger safety:
// nothing fires on the row tap itself) → Confirm runs the single-device forced plan
// server-side (idempotence guards bypassed via force, toggles claim their target).
import { useState } from 'react';
import { useReconcilePreview, useForceReconcileDevice } from '../hooks/useApi';
import { useLogStore } from '../stores/useLogStore';
import type { ReconcilePreviewRow, ReconcilePlanStep } from '../types/api';

interface Props {
  scenarioId: string;
  open: boolean;
  onClose: () => void;
}

type RowResult = { ok: boolean; message: string };

// believed/desired come through the contract as `unknown` (power may be a per-zone
// object for the eMotiva). Render compactly either way.
function fmtValue(v: unknown): string {
  if (v === null || v === undefined) return '?';
  if (typeof v === 'object') {
    return Object.entries(v as Record<string, unknown>)
      .map(([zone, val]) => `z${zone}:${fmtValue(val)}`)
      .join(' ');
  }
  return String(v);
}

function fmtStep(s: ReconcilePlanStep): string {
  const parts: string[] = [];
  if (s.pre_delay_ms) parts.push(`wait ${(s.pre_delay_ms / 1000).toFixed(1)}s`);
  parts.push(s.command);
  if (s.feedback && s.poll_timeout_ms) parts.push(`(confirm ≤${Math.round(s.poll_timeout_ms / 1000)}s)`);
  else if (s.delay_ms) parts.push(`(+${(s.delay_ms / 1000).toFixed(1)}s settle)`);
  return parts.join(' ');
}

export function ForceReconcileDialog({ scenarioId, open, onClose }: Props) {
  const addLog = useLogStore((s) => s.addLog);
  const { data, isLoading, isError } = useReconcilePreview(scenarioId, open);
  const force = useForceReconcileDevice();
  const [expanded, setExpanded] = useState<string | null>(null);
  const [pending, setPending] = useState<string | null>(null);
  const [results, setResults] = useState<Record<string, RowResult>>({});

  if (!open) return null;

  const close = () => {
    setExpanded(null);
    setResults({});
    setPending(null);  // UI-14 (#19): clear in-flight state so a quick reopen isn't stranded
    onClose();
  };

  const confirm = async (deviceId: string) => {
    setPending(deviceId);
    try {
      const resp = await force.mutateAsync({ scenarioId, deviceId });
      const message = resp.success
        ? `Done — ${resp.executed.length} command(s) sent`
        : resp.failures.map((f) => `${f.command}: ${f.error}`).join('; ');
      setResults((prev) => ({ ...prev, [deviceId]: { ok: resp.success, message } }));
      addLog({
        level: resp.success ? 'info' : 'error',
        message: `Force-reconcile ${deviceId} (${scenarioId}): ${message}`,
      });
    } catch (err: unknown) {
      const e = err as { response?: { data?: { detail?: string } } };
      const message = e.response?.data?.detail ?? 'request failed';
      setResults((prev) => ({ ...prev, [deviceId]: { ok: false, message } }));
      addLog({ level: 'error', message: `Force-reconcile ${deviceId} failed: ${message}` });
    }
    setPending(null);
  };

  const renderRow = (row: ReconcilePreviewRow) => {
    const isExpanded = expanded === row.device_id;
    const isPending = pending === row.device_id;
    const result = results[row.device_id];
    const tappable = row.reconcilable && !pending;

    return (
      <div
        key={row.device_id}
        className={`rounded-md border px-3 py-2 ${
          row.in_sync ? 'border-border' : 'border-amber-400/60 bg-amber-500/10'
        } ${row.reconcilable ? '' : 'opacity-50'}`}
      >
        <button
          className="w-full text-left disabled:cursor-default"
          disabled={!tappable}
          onClick={() => setExpanded(isExpanded ? null : row.device_id)}
        >
          <div className="flex items-center justify-between gap-2">
            <span className="text-sm font-medium truncate">{row.device_name}</span>
            <span className={`text-xs shrink-0 ${row.in_sync ? 'text-muted-foreground' : 'text-amber-400'}`}>
              {row.in_sync ? 'in sync (per state)' : 'out of sync'}
            </span>
          </div>
          <div className="mt-1 space-y-0.5">
            {row.comparisons.map((c) => (
              <div key={c.domain} className="text-xs text-muted-foreground">
                {c.domain}:{' '}
                {c.in_sync ? (
                  <span>{fmtValue(c.believed)}</span>
                ) : (
                  <span>
                    <span className="text-amber-400">{fmtValue(c.believed)}</span>
                    {' → '}
                    <span>{fmtValue(c.desired)}</span>
                  </span>
                )}
              </div>
            ))}
            {!row.reconcilable && (
              <div className="text-xs text-muted-foreground italic">not reconcilable</div>
            )}
          </div>
        </button>

        {isExpanded && row.reconcilable && (
          <div className="mt-2 border-t border-border pt-2">
            <div className="text-xs text-muted-foreground space-y-0.5">
              {row.steps.map((s, i) => (
                <div key={i}>{i + 1}. {fmtStep(s)}</div>
              ))}
              <div className="pt-0.5">
                up to ~{Math.max(1, Math.round(row.eta_ms / 1000))}s total
              </div>
            </div>
            <div className="mt-2 flex items-center justify-between gap-2">
              <span className={`text-xs ${result ? (result.ok ? 'text-green-500' : 'text-red-400') : 'text-transparent'}`}>
                {result?.message ?? '.'}
              </span>
              <button
                className="px-3 py-1 text-xs rounded-md bg-amber-600 hover:bg-amber-500 text-white disabled:opacity-50 shrink-0"
                disabled={isPending || pending !== null}
                onClick={() => void confirm(row.device_id)}
              >
                {isPending ? 'Sending…' : 'Send anyway'}
              </button>
            </div>
          </div>
        )}
      </div>
    );
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50" onClick={close}>
      <div
        className="w-full max-w-md mx-4 max-h-[80vh] overflow-y-auto bg-popover border border-border rounded-md shadow-lg p-4"
        onClick={(e) => e.stopPropagation()}
      >
        <h2 className="text-sm font-semibold mb-1">Device states — {scenarioId}</h2>
        <p className="text-xs text-muted-foreground mb-3">
          What the bridge believes vs what this scenario wants. If a device disagrees
          with what you see in the room, tap its row and send the commands anyway —
          the bridge can't sense it, but you can.
        </p>

        {isLoading && <p className="text-sm text-muted-foreground">Loading…</p>}
        {isError && (
          <p className="text-sm text-amber-400">
            Couldn't load the preview — is this scenario still active?
          </p>
        )}

        <div className="space-y-2">{data?.devices.map(renderRow)}</div>

        <div className="flex justify-end mt-3">
          <button className="px-3 py-1.5 text-sm rounded-md bg-accent hover:bg-accent/80" onClick={close}>
            Close
          </button>
        </div>
      </div>
    </div>
  );
}
