// Layer 3 (Step 2): adapt the backend-served LayoutManifest into the renderer's
// RemoteDeviceStructure, resolving icons UI-side.
//
// The backend manifest mirrors RemoteDeviceStructure 1:1 (camelCase), so the existing
// RemoteControlLayout consumes it unchanged. Two seams the backend deliberately leaves
// to the UI:
//   1. Icons — the engine emits placeholder icons (iconLibrary "fallback"); the UI's
//      IconResolver maps actionName -> glyph at render time (keeps the manifest
//      skin-agnostic; decided 2026-05-23). This matches the build-time codegen, which
//      bakes IconResolver output into the .gen.tsx pages.
//   2. stateInterface — null in the manifest (carryover field, unused by the renderer);
//      stubbed here to satisfy the type.
import { IconResolver } from './IconResolver';
import type { LayoutManifest } from '../hooks/useApi';
import type {
  RemoteDeviceStructure,
  RemoteZone,
  ZoneContent,
} from '../types/RemoteControlLayout';
import type {
  ProcessedAction,
  StateDefinition,
  ActionHandler,
  ActionIcon,
} from '../types/ProcessedDevice';

const iconResolver = new IconResolver();

// The renderer requires stateInterface but never reads it (verified); stub for the type.
const EMPTY_STATE_INTERFACE: StateDefinition = {
  interfaceName: '',
  fields: [],
  imports: [],
  extends: [],
};

function resolveIcon(actionName: string): ActionIcon {
  // mirror the codegen: material library (see deviceHandlers/*Handler.ts)
  return iconResolver.selectIconForActionWithLibrary(actionName, 'material');
}

function resolveActionIcon(action: ProcessedAction | undefined): void {
  if (action) action.icon = resolveIcon(action.actionName);
}

function resolveZoneContent(content: ZoneContent): void {
  content.powerButtons?.forEach((b) => resolveActionIcon(b.action));
  content.playbackSection?.actions.forEach(resolveActionIcon);
  content.tracksSection?.actions.forEach(resolveActionIcon);
  content.screenActions?.forEach(resolveActionIcon);
  if (content.volumeSlider) {
    resolveActionIcon(content.volumeSlider.action);
    resolveActionIcon(content.volumeSlider.muteAction);
  }
  content.volumeButtons?.forEach((b) => {
    resolveActionIcon(b.upAction);
    resolveActionIcon(b.downAction);
    resolveActionIcon(b.muteAction);
  });
  if (content.navigationCluster) {
    Object.values(content.navigationCluster).forEach((a) => resolveActionIcon(a));
  }
  if (content.pointerPad) {
    resolveActionIcon(content.pointerPad.moveAction);
    resolveActionIcon(content.pointerPad.clickAction);
    resolveActionIcon(content.pointerPad.dragAction);
    resolveActionIcon(content.pointerPad.scrollAction);
  }
  // inputs/apps dropdowns carry only string actions (no icons) — nothing to resolve.
}

export function manifestToDeviceStructure(manifest: LayoutManifest): RemoteDeviceStructure {
  // Clone so we never mutate the React-Query cache while resolving icons in place.
  // The manifest is plain JSON and structurally identical to RemoteZone[] (the type
  // seam between the OpenAPI-generated and hand-written mirror types lives here).
  const remoteZones = JSON.parse(JSON.stringify(manifest.remoteZones ?? [])) as RemoteZone[];
  remoteZones.forEach((zone) => resolveZoneContent(zone.content));

  return {
    deviceId: manifest.deviceId,
    deviceName: manifest.deviceName,
    deviceClass: manifest.deviceClass,
    remoteZones,
    stateInterface: (manifest.stateInterface as StateDefinition | null) ?? EMPTY_STATE_INTERFACE,
    actionHandlers: (manifest.actionHandlers ?? []) as unknown as ActionHandler[],
    specialCases: manifest.specialCases as RemoteDeviceStructure['specialCases'],
  };
}
