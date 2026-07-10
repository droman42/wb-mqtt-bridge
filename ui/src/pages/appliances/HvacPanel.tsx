// Native HVAC panel (§P3.7 #26 Phase 3; reshaped for DRV-28). Mirrors the mitsubishi2wb
// firmware's /control page — mode/fan/vane/widevane button grids, setpoint number input,
// read-only room temperature. Reads value-label tables from /system/catalog so the option
// grids are self-describing (wire payload + canonical identifier + per-locale label);
// posts canonical actions back via POST /devices/{id}/canonical. Same generic component
// services all 3 Mitsubishi HVAC instances (bedroom / living_room / children_room) —
// the device_id comes from the React-router param, and each device's catalog entry
// supplies the vocabulary.
//
// DRV-28 contract shape: SIX per-domain capabilities — power {on,off} ·
// mode/fan/vane/widevane {set {value}} · temperature {set {value}} + readonly
// room_temperature. State fields are top-level canonical values (`state.mode === "cool"`,
// `state.power === "on"`, `state.setpoint`).
//
// UI-16: value icons resolve through the shared IconResolver (the same mechanism AV
// button icons use), keyed by canonical value — approved item-by-item in the
// three-iteration icon review (2026-07-10). dry/cool/heat carry fixed colors (the
// firmware shows colored emoji); everything else renders theme ink via currentColor.
import { useEffect, useMemo } from 'react';
import { useParams } from 'react-router-dom';
import { useSystemCatalog, useExecuteCanonicalAction } from '../../hooks/useApi';
import { useDeviceState } from '../../hooks/useDeviceState';
import { useSettingsStore } from '../../stores/useSettingsStore';
import { useRoomStore } from '../../stores/useRoomStore';
import { useLogStore } from '../../stores/useLogStore';
import { Button } from '../../components/ui/button';
import { Icon } from '../../components/icons';
import { IconResolver } from '../../lib/IconResolver';
import type { components } from '../../types/openapi.gen';

type CatalogValueLabel = components['schemas']['CatalogValueLabel'];

const iconResolver = new IconResolver();

function labelOf(entry: CatalogValueLabel, language: 'en' | 'ru'): string {
  // Catalog labels are {ru, en, de, ...}; settings store carries en/ru today. Fall back
  // to en, then to the canonical identifier (legible) when labels are absent.
  return entry.labels?.[language] ?? entry.labels?.en ?? entry.canonical;
}

/** UI-16: one enum-value icon, resolver-driven. Fixed-color entries (dry/cool/heat)
 * wrap the icon in a colored span — currentColor picks it up in every button state;
 * everything else stays theme ink. Unmapped values fall back to a neutral dot. */
function ValueIcon({ capability, value }: { capability: string; value: string }) {
  const resolved = iconResolver.resolveValueIcon(capability, value);
  if (!resolved) return <span className="text-lg leading-none">·</span>;
  const icon = (
    <Icon library={resolved.library} name={resolved.name} fallback={resolved.fallback} size="md" />
  );
  return resolved.color
    ? <span style={{ color: resolved.color }} className="leading-none">{icon}</span>
    : <span className="leading-none">{icon}</span>;
}

export function HvacPanel() {
  const { deviceId } = useParams<{ deviceId: string }>();
  const { addLog } = useLogStore();
  const { selectDevice } = useRoomStore();
  const { language, statePanelOpen } = useSettingsStore();
  const catalog = useSystemCatalog();
  const { state } = useDeviceState(deviceId ?? '');
  const execute = useExecuteCanonicalAction();

  useEffect(() => {
    if (deviceId) selectDevice(deviceId);
  }, [deviceId, selectDevice]);

  // DRV-28: six per-domain capabilities, keyed by name.
  const caps = useMemo(() => {
    if (!catalog.data || !deviceId) return undefined;
    const dev = catalog.data.devices.find(d => d.id === deviceId);
    if (!dev?.capabilities) return undefined;
    return new Map(dev.capabilities.map(c => [c.name, c]));
  }, [catalog.data, deviceId]);

  if (!deviceId) {
    return <div className="p-6 text-center text-muted-foreground">No device id.</div>;
  }
  if (catalog.isLoading) {
    return <div className="p-6 text-center text-muted-foreground">Loading…</div>;
  }
  if (!caps?.has('mode') || !caps.has('power')) {
    return <div className="p-6 text-center text-muted-foreground">No HVAC capabilities for {deviceId}.</div>;
  }

  // State fields are top-level CANONICAL values (MitsubishiHvacState).
  const st = (state ?? {}) as unknown as Record<string, unknown>;
  const power = st.power === 'on';
  const setpoint = typeof st.setpoint === 'number' ? st.setpoint : undefined;
  const roomTemp = typeof st.room_temperature === 'number' ? st.room_temperature : undefined;
  const pending = execute.isPending;

  const dispatch = (capability: string, action: string, params?: Record<string, unknown>) => {
    if (!deviceId) return;
    execute.mutate({
      deviceId,
      // wait:true — the panel merges the echoed post-action state into the cache.
      request: { capability, action, params: params ?? null, wait: true },
    });
    addLog({ level: 'info', message: `${capability}.${action} -> ${deviceId}`, details: params });
  };

  const renderEnumGrid = (capName: string) => {
    const cap = caps.get(capName);
    const field = cap?.fields?.find(f => f.name === capName);
    if (!field?.values?.length) return null;
    const raw = st[capName];
    const current = typeof raw === 'string' ? raw : undefined;
    const title = field.labels?.[language] ?? field.labels?.en ?? capName;
    return (
      <section key={capName} className="rounded-lg border border-border p-4 space-y-3">
        <div className="text-sm font-medium">{title}</div>
        <div className="grid grid-cols-3 gap-2 sm:grid-cols-4 md:grid-cols-7">
          {field.values.map(v => {
            const selected = current === v.canonical;
            return (
              <Button
                key={v.canonical}
                variant={selected ? 'default' : 'outline'}
                disabled={pending}
                onClick={() => dispatch(capName, 'set', { value: v.canonical })}
                className="flex h-auto flex-col items-center gap-1 px-2 py-2 text-xs"
              >
                <ValueIcon capability={capName} value={v.canonical} />
                <span className="leading-tight text-center">{labelOf(v, language)}</span>
              </Button>
            );
          })}
        </div>
      </section>
    );
  };

  const temperatureCap = caps.get('temperature');
  const setpointField = temperatureCap?.fields?.find(f => f.name === 'setpoint');
  const roomTempField = temperatureCap?.fields?.find(f => f.name === 'room_temperature');
  const minSetpoint = 16, maxSetpoint = 31;  // mitsubishi2wb firmware default range

  return (
    <div className={`${statePanelOpen ? 'p-2' : 'p-4'}`}>
      <div className="mx-auto w-full max-w-3xl space-y-4">
        <h1 className="text-lg font-bold text-center tracking-wide">{deviceId.replace(/_/g, ' ')}</h1>

        {/* Power */}
        <section className="rounded-lg border border-border p-4 space-y-3">
          <div className="text-sm font-medium">{language === 'ru' ? 'Питание' : 'Power'}</div>
          <Button
            variant={power ? 'default' : 'outline'}
            disabled={pending}
            onClick={() => dispatch('power', power ? 'off' : 'on')}
            className="w-full flex items-center justify-center gap-2"
          >
            <ValueIcon capability="power" value={power ? 'off' : 'on'} />
            {power ? (language === 'ru' ? 'Включено' : 'On') : (language === 'ru' ? 'Выключено' : 'Off')}
          </Button>
        </section>

        {/* Setpoint + room temperature */}
        <section className="rounded-lg border border-border p-4 space-y-3">
          <div className="text-sm font-medium">
            {setpointField?.labels?.[language] ?? setpointField?.labels?.en ?? 'Setpoint'}
            {setpointField?.unit ? ` (${setpointField.unit})` : ''}
          </div>
          <div className="flex items-center gap-3">
            <input
              type="number"
              min={minSetpoint}
              max={maxSetpoint}
              step={0.5}
              disabled={pending}
              defaultValue={setpoint}
              key={setpoint}  // re-mount when the state echo arrives so the input reflects it
              onBlur={(e) => {
                const v = parseFloat(e.target.value);
                if (!Number.isNaN(v) && v !== setpoint) {
                  dispatch('temperature', 'set', { value: v });
                }
              }}
              className="w-24 rounded-md border border-input bg-background px-3 py-2 text-sm"
            />
            {roomTemp !== undefined && (
              <span className="text-sm text-muted-foreground">
                {roomTempField?.labels?.[language] ?? roomTempField?.labels?.en ?? 'Room temperature'}:&nbsp;
                <span className="font-medium tabular-nums">{roomTemp.toFixed(1)}{roomTempField?.unit ?? '°C'}</span>
              </span>
            )}
          </div>
        </section>

        {renderEnumGrid('mode')}
        {renderEnumGrid('fan')}
        {renderEnumGrid('vane')}
        {renderEnumGrid('widevane')}
      </div>
    </div>
  );
}

export default HvacPanel;
