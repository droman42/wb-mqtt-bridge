/* Voice readiness — the first real page of the v1 cut (workbench_split.md §2.3):
   existing read/action surfaces only. Catalog version + a test-utterance pane firing
   the already-shipped POST /devices/{id}/canonical. Also hosts the backend-target
   override (the "workbench-level configuration" §2.2 assigns the target address to). */

import { useCallback, useEffect, useMemo, useState } from 'react';
import {
  Alert,
  AlertDescription,
  Button,
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  Checkbox,
  Input,
  Label,
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from 'locveil-ui-kit';
import type { PageProps } from 'locveil-workbench/contract';
import {
  api,
  apiBase,
  hasApiBaseOverride,
  setApiBaseOverride,
  type CatalogResponse,
  type SystemInfo,
} from '@/api';
import { t, pickName } from '@/i18n';

export default function VoiceReadinessPage({ locale }: PageProps) {
  const [catalog, setCatalog] = useState<CatalogResponse | null>(null);
  const [system, setSystem] = useState<SystemInfo | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);

  const [deviceId, setDeviceId] = useState('');
  const [capability, setCapability] = useState('');
  const [action, setAction] = useState('');
  const [paramsText, setParamsText] = useState('');
  const [wait, setWait] = useState(true);
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<string | null>(null);
  const [resultError, setResultError] = useState(false);

  const [baseDraft, setBaseDraft] = useState(apiBase());

  const load = useCallback(async () => {
    setLoadError(null);
    try {
      const [cat, sys] = await Promise.all([api.getCatalog(), api.getSystem()]);
      setCatalog(cat);
      setSystem(sys);
    } catch (e) {
      setCatalog(null);
      setSystem(null);
      setLoadError(e instanceof Error ? e.message : String(e));
    }
  }, []);

  useEffect(() => {
    void load();
  }, [load]);

  const device = useMemo(
    () => catalog?.devices.find((d) => d.id === deviceId),
    [catalog, deviceId]
  );
  const cap = useMemo(
    () => device?.capabilities?.find((c) => c.name === capability),
    [device, capability]
  );
  const actions = cap?.actions ?? [];

  const fire = async () => {
    if (!deviceId || !capability || !action) return;
    let params: Record<string, unknown> | null = null;
    if (paramsText.trim()) {
      try {
        params = JSON.parse(paramsText) as Record<string, unknown>;
      } catch {
        setResult(t(locale, { ru: 'params: некорректный JSON', en: 'params: invalid JSON' }));
        setResultError(true);
        return;
      }
    }
    setBusy(true);
    setResult(null);
    try {
      const res = await api.canonical(deviceId, { capability, action, params, wait });
      setResult(JSON.stringify(res, null, 2));
      setResultError(false);
    } catch (e) {
      setResult(e instanceof Error ? e.message : String(e));
      setResultError(true);
    } finally {
      setBusy(false);
    }
  };

  const applyBase = () => {
    setApiBaseOverride(baseDraft === apiBase() && !hasApiBaseOverride() ? null : baseDraft);
    void load();
  };

  return (
    <div className="max-w-3xl space-y-4 p-4">
      <Card>
        <CardHeader>
          <CardTitle>{t(locale, { ru: 'Контроллер', en: 'Controller' })}</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="flex items-end gap-2">
            <div className="grow space-y-1">
              <Label htmlFor="api-base">
                {t(locale, { ru: 'Адрес API моста', en: 'Bridge API address' })}
              </Label>
              <Input
                id="api-base"
                value={baseDraft}
                onChange={(e) => setBaseDraft(e.target.value)}
                className="font-mono"
              />
            </div>
            <Button onClick={applyBase}>
              {t(locale, { ru: 'Подключиться', en: 'Connect' })}
            </Button>
          </div>
          {loadError ? (
            <Alert variant="destructive">
              <AlertDescription>
                {t(locale, { ru: 'Нет связи с мостом: ', en: 'Bridge unreachable: ' })}
                {loadError}
              </AlertDescription>
            </Alert>
          ) : (
            <dl className="grid grid-cols-2 gap-x-6 gap-y-1 text-sm">
              <dt className="text-muted-foreground">
                {t(locale, { ru: 'Версия моста', en: 'Bridge version' })}
              </dt>
              <dd className="tabular-nums">{system?.version ?? '…'}</dd>
              <dt className="text-muted-foreground">
                {t(locale, { ru: 'Версия каталога', en: 'Catalog version' })}
              </dt>
              <dd className="tabular-nums">{catalog?.version ?? '…'}</dd>
              <dt className="text-muted-foreground">
                {t(locale, { ru: 'Устройств в каталоге', en: 'Devices in catalog' })}
              </dt>
              <dd className="tabular-nums">{catalog?.devices.length ?? '…'}</dd>
            </dl>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>
            {t(locale, { ru: 'Тест канонической команды', en: 'Canonical command test' })}
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <p className="text-sm text-muted-foreground">
            {t(locale, {
              ru: 'Прогоняет команду тем же путём, каким её шлёт голосовой ассистент: POST /devices/{id}/canonical.',
              en: 'Runs a command through the same path the voice assistant uses: POST /devices/{id}/canonical.',
            })}
          </p>
          <div className="grid grid-cols-3 gap-3">
            <div className="space-y-1">
              <Label>{t(locale, { ru: 'Устройство', en: 'Device' })}</Label>
              <Select
                value={deviceId}
                onValueChange={(v) => {
                  setDeviceId(v);
                  setCapability('');
                  setAction('');
                }}
              >
                <SelectTrigger>
                  <SelectValue placeholder="—" />
                </SelectTrigger>
                <SelectContent>
                  {(catalog?.devices ?? []).map((d) => (
                    <SelectItem key={d.id} value={d.id}>
                      {pickName(locale, d.names, d.id)}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1">
              <Label>{t(locale, { ru: 'Возможность', en: 'Capability' })}</Label>
              <Select
                value={capability}
                onValueChange={(v) => {
                  setCapability(v);
                  setAction('');
                }}
                disabled={!device}
              >
                <SelectTrigger>
                  <SelectValue placeholder="—" />
                </SelectTrigger>
                <SelectContent>
                  {(device?.capabilities ?? [])
                    .filter((c) => (c.actions ?? []).length > 0)
                    .map((c) => (
                      <SelectItem key={c.name} value={c.name}>
                        {c.name}
                      </SelectItem>
                    ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1">
              <Label>{t(locale, { ru: 'Действие', en: 'Action' })}</Label>
              <Select value={action} onValueChange={setAction} disabled={!cap}>
                <SelectTrigger>
                  <SelectValue placeholder="—" />
                </SelectTrigger>
                <SelectContent>
                  {actions.map((a) => (
                    <SelectItem key={a.name} value={a.name}>
                      {a.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>
          <div className="space-y-1">
            <Label htmlFor="params">
              {t(locale, { ru: 'Параметры (JSON, необязательно)', en: 'Params (JSON, optional)' })}
            </Label>
            <Input
              id="params"
              value={paramsText}
              onChange={(e) => setParamsText(e.target.value)}
              placeholder='{"level": 30}'
              className="font-mono"
            />
          </div>
          <div className="flex items-center gap-4">
            <label className="flex items-center gap-2 text-sm">
              <Checkbox checked={wait} onCheckedChange={(v) => setWait(v === true)} />
              {t(locale, { ru: 'ждать подтверждения', en: 'wait for confirmation' })}
            </label>
            <Button onClick={() => void fire()} disabled={!action || busy}>
              {busy
                ? t(locale, { ru: 'Выполняется…', en: 'Running…' })
                : t(locale, { ru: 'Выполнить', en: 'Run' })}
            </Button>
          </div>
          {result !== null && (
            <Alert variant={resultError ? 'destructive' : 'default'}>
              <AlertDescription>
                <pre className="max-h-64 overflow-auto whitespace-pre-wrap text-xs">{result}</pre>
              </AlertDescription>
            </Alert>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
