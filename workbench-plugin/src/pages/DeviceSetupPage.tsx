/* Device setup — v1 shell (workbench_split.md §2.3): the configured-device inventory
   from the existing read surface GET /config/devices, with every config-writing verb
   dormant under PROD-4-auth. The deep features (wb-webui.conf importer, IR-code save)
   stay in their planned page designs and file as their own tasks when pulled. */

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
import { api, type BaseDeviceConfig } from '@/api';
import { t, pickName } from '@/i18n';
import { DormantVerb } from '@/components/DormantVerb';

export default function DeviceSetupPage({ locale }: PageProps) {
  const [devices, setDevices] = useState<Record<string, BaseDeviceConfig> | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .getDeviceConfigs()
      .then(setDevices)
      .catch((e: unknown) => setError(e instanceof Error ? e.message : String(e)));
  }, []);

  return (
    <div className="max-w-3xl space-y-4 p-4">
      <Card>
        <CardHeader>
          <CardTitle>
            {t(locale, { ru: 'Настроенные устройства', en: 'Configured devices' })}
          </CardTitle>
        </CardHeader>
        <CardContent>
          {error && (
            <Alert variant="destructive">
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          )}
          {devices && (
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b text-left text-muted-foreground">
                  <th className="py-1 pr-3 font-medium">id</th>
                  <th className="py-1 pr-3 font-medium">
                    {t(locale, { ru: 'Название', en: 'Name' })}
                  </th>
                  <th className="py-1 pr-3 font-medium">
                    {t(locale, { ru: 'Класс', en: 'Class' })}
                  </th>
                  <th className="py-1 font-medium">
                    {t(locale, { ru: 'Комната', en: 'Room' })}
                  </th>
                </tr>
              </thead>
              <tbody>
                {Object.values(devices).map((d) => (
                  <tr key={d.device_id} className="border-b border-border/50">
                    <td className="py-1 pr-3 font-mono text-xs">{d.device_id}</td>
                    <td className="py-1 pr-3">
                      {pickName(locale, d.names as Record<string, string>, d.device_id)}
                    </td>
                    <td className="py-1 pr-3">{d.device_class}</td>
                    <td className="py-1">{d.room ?? '—'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>{t(locale, { ru: 'Изменения', en: 'Changes' })}</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <p className="text-sm text-muted-foreground">
            {t(locale, {
              ru: 'Запись конфигурации откроется после решения по авторизации; кнопки показывают свой гейт честно.',
              en: 'Config writes open up after the auth decision lands; the buttons show their gate honestly.',
            })}
          </p>
          <div className="flex flex-wrap gap-3">
            <DormantVerb
              label={t(locale, { ru: 'Импорт из wb-webui.conf', en: 'Import from wb-webui.conf' })}
            />
            <DormantVerb
              label={t(locale, { ru: 'Сохранить ИК-коды', en: 'Save IR codes' })}
            />
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
