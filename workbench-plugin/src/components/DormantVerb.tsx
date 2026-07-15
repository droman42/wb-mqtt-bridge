/* A config-writing verb rendered dormant under its named gate (contract honesty
   rule, workbench.md §4: disabled with the gate named, never hidden). Every write
   verb in the v1 cut carries the gate `PROD-4-auth` (workbench_split.md §2.2). */

import { Button, StatusChip } from 'locveil-ui-kit';

export const WRITE_GATE = 'PROD-4-auth';

export function DormantVerb({ label }: { label: string }) {
  return (
    <span className="inline-flex items-center gap-2">
      <Button disabled title={WRITE_GATE}>
        {label}
      </Button>
      <StatusChip variant="pristine">{WRITE_GATE}</StatusChip>
    </span>
  );
}
