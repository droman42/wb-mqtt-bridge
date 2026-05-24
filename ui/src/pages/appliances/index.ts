// Hand-written bespoke appliance pages, keyed by device_id (device_category=appliance). Appliances
// are out of the Layer-3 A/V remote/manifest model (no capability map → the runtime renderer would
// be empty), so they do NOT go through RuntimeDevicePage — App.tsx routes them here. Add a new
// appliance by writing its page component and registering it below. See ui_backend_contract.md
// "Step 4 — cutover".
import type { ComponentType } from 'react';
import { KitchenHoodPage } from './KitchenHoodPage';

const APPLIANCE_PAGES: Record<string, ComponentType> = {
  kitchen_hood: KitchenHoodPage,
};

export const getAppliancePage = (deviceId: string): ComponentType | undefined =>
  APPLIANCE_PAGES[deviceId];
