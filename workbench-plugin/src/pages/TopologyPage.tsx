/* Topology setup — v1 shell (workbench_split.md §2.3): rooms + their devices from the
   existing read surface GET /room/list; the save verb is dormant under PROD-4-auth.
   The graph editor and the topology read/preview endpoints arrive with their planned
   page when pulled ("Apply" will stage, never write live — §3). */

import { useEffect, useState } from 'react';
import {
  Alert,
  AlertDescription,
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from 'locveil-ui-kit';
import type { PageProps } from 'locveil-workbench/contract';
import { api, type RoomDefinitionResponse } from '@/api';
import { t, pickName } from '@/i18n';
import { DormantVerb } from '@/components/DormantVerb';

export default function TopologyPage({ locale }: PageProps) {
  const [rooms, setRooms] = useState<RoomDefinitionResponse[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .listRooms()
      .then(setRooms)
      .catch((e: unknown) => setError(e instanceof Error ? e.message : String(e)));
  }, []);

  return (
    <div className="max-w-3xl space-y-4 p-4">
      <Card>
        <CardHeader>
          <CardTitle>{t(locale, { ru: 'Комнаты', en: 'Rooms' })}</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          {error && (
            <Alert variant="destructive">
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          )}
          {rooms?.map((r) => (
            <div key={r.room_id} className="rounded-md border border-border/60 p-3">
              <div className="flex items-baseline justify-between">
                <span className="font-medium">
                  {pickName(locale, r.names, r.room_id)}
                </span>
                <span className="font-mono text-xs text-muted-foreground">{r.room_id}</span>
              </div>
              <p className="mt-1 text-sm text-muted-foreground">
                {r.devices.length
                  ? r.devices.join(', ')
                  : t(locale, { ru: 'без устройств', en: 'no devices' })}
              </p>
            </div>
          ))}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>{t(locale, { ru: 'Изменения', en: 'Changes' })}</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <p className="text-sm text-muted-foreground">
            {t(locale, {
              ru: '«Применить» будет создавать отложенное предложение — рабочая конфигурация через этот экран не изменяется никогда.',
              en: '"Apply" will stage a proposal — the running config is never written through this screen.',
            })}
          </p>
          <DormantVerb
            label={t(locale, { ru: 'Сохранить топологию', en: 'Save topology' })}
          />
        </CardContent>
      </Card>
    </div>
  );
}
