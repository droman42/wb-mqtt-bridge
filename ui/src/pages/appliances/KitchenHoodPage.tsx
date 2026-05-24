// Bespoke appliance page for the Broadlink kitchen hood. Appliances are out of the Layer-3 A/V
// remote model (no capability map / zone layout), so they get hand-written pages — see
// ui_backend_contract.md "Step 4 — cutover". This replaces the (empty) build-time generated page:
// the generated structure had all-empty zones, and its controls had relied on a `specialCases`
// back-channel the renderer no longer reads. Controls: light on/off (set_light {state}) + fan
// speed 0–4 (set_speed {level}); live values come from the device state (light, speed).
import { useEffect } from 'react';
import { useExecuteDeviceAction } from '../../hooks/useApi';
import { useDeviceState } from '../../hooks/useDeviceState';
import { useSettingsStore } from '../../stores/useSettingsStore';
import { useRoomStore } from '../../stores/useRoomStore';
import { useLogStore } from '../../stores/useLogStore';
import { Button } from '../../components/ui/button';
import { Icon } from '../../components/icons';

const DEVICE_ID = 'kitchen_hood';
const SPEEDS = [0, 1, 2, 3, 4];

export function KitchenHoodPage() {
  const { addLog } = useLogStore();
  const executeAction = useExecuteDeviceAction();
  const { state } = useDeviceState(DEVICE_ID);
  const { statePanelOpen } = useSettingsStore();
  const { selectDevice } = useRoomStore();

  useEffect(() => {
    selectDevice(DEVICE_ID);
  }, [selectDevice]);

  const dispatch = (action: string, params: Record<string, unknown>) => {
    executeAction.mutate({ deviceId: DEVICE_ID, action: { action, params } });
    addLog({ level: 'info', message: `Action: ${action} -> ${DEVICE_ID}`, details: params });
  };

  const lightOn = (state as { light?: string })?.light === 'on';
  const rawSpeed = (state as { speed?: number })?.speed;
  const speed = typeof rawSpeed === 'number' ? rawSpeed : 0;
  const pending = executeAction.isPending;

  return (
    <div className={`${statePanelOpen ? 'p-2' : 'p-4'}`}>
      <div className="mx-auto w-full max-w-md space-y-6">
        <h1 className="text-lg font-bold text-center tracking-wide">Kitchen Hood</h1>

        {/* Light */}
        <section className="rounded-lg border border-border p-4 space-y-3">
          <div className="flex items-center space-x-2">
            <Icon library="material" name="Lightbulb" fallback="light" size="md" className="h-5 w-5 text-muted-foreground" />
            <span className="text-sm font-medium">Light</span>
          </div>
          <Button
            variant={lightOn ? 'default' : 'outline'}
            disabled={pending}
            onClick={() => dispatch('set_light', { state: lightOn ? 'off' : 'on' })}
            className="w-full"
          >
            {lightOn ? 'On' : 'Off'}
          </Button>
        </section>

        {/* Fan speed */}
        <section className="rounded-lg border border-border p-4 space-y-3">
          <div className="flex items-center space-x-2">
            <Icon library="custom" name="fan" fallback="fan" size="md" className="h-5 w-5 text-muted-foreground" />
            <span className="text-sm font-medium">Fan Speed</span>
          </div>
          <div className="grid grid-cols-5 gap-2">
            {SPEEDS.map((n) => (
              <Button
                key={n}
                variant={speed === n ? 'default' : 'outline'}
                disabled={pending}
                onClick={() => dispatch('set_speed', { level: n })}
              >
                {n === 0 ? 'Off' : n}
              </Button>
            ))}
          </div>
        </section>
      </div>
    </div>
  );
}

export default KitchenHoodPage;
