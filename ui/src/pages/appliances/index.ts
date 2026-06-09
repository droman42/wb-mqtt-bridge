// Hand-written bespoke pages, keyed by device_id. The Layer-3 manifest only models A/V
// remote-style layouts (buttons, sliders, pointer pads); devices whose shape doesn't fit
// (kitchen hood appliance + the 3 Mitsubishi HVACs, which need value-table-driven mode/
// fan/vane/widevane dropdowns from §P3.7 #26) get hand-written pages routed here from
// App.tsx → DevicePage. Add a new bespoke page by writing its component and
// registering it below. See ui_backend_contract.md "Step 4 — cutover".
import type { ComponentType } from 'react';
import { KitchenHoodPage } from './KitchenHoodPage';
import { HvacPanel } from './HvacPanel';

const APPLIANCE_PAGES: Record<string, ComponentType> = {
  kitchen_hood: KitchenHoodPage,
  // §P3.7 #26 Phase 3 — Mitsubishi HVAC instances. Same generic HvacPanel for all 3;
  // the device_id from the React-router param selects which catalog entry to read.
  bedroom_hvac: HvacPanel,
  living_room_hvac: HvacPanel,
  children_room_hvac: HvacPanel,
};

export const getAppliancePage = (deviceId: string): ComponentType | undefined =>
  APPLIANCE_PAGES[deviceId];
