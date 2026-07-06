// Remote Control Layout Types - Phase 1
// Zone-based architecture for device remote control interfaces

import type { ProcessedAction } from './ProcessedDevice';

export type ZoneType = 'power' | 'media-stack' | 'screen' | 'volume' | 'apps' | 'menu' | 'pointer';
export type ZoneId = 'power' | 'media-stack' | 'screen' | 'volume' | 'apps' | 'menu' | 'pointer';

export interface RemoteZone {
  zoneId: ZoneId;
  zoneName: string;
  zoneType: ZoneType;
  showHide: boolean; // true = show/hide based on device config, false = always present
  isEmpty: boolean;
  enabled?: boolean; // Controls whether the zone should be rendered
  content: ZoneContent;
  layout: ZoneLayoutConfig;
}

export interface ZoneContent {
  // Power Zone (①)
  powerButtons?: PowerButtonConfig[];
  
  // Media Stack Zone (②)
  inputsDropdown?: DropdownConfig;
  playbackSection?: PlaybackConfig;
  tracksSection?: TracksConfig;
  
  // Screen Zone (③) - Vertical button alignment
  screenActions?: ProcessedAction[];
  
  // Volume Zone (④) - Priority-based population
  volumeSlider?: VolumeSliderConfig;
  volumeButtons?: VolumeButtonConfig[];
  
  // Apps Zone (⑤)
  appsDropdown?: DropdownConfig;
  
  // Menu Navigation Zone (⑦) - Central navigation
  navigationCluster?: NavigationClusterConfig;
  
  // Pointer Zone (⑥)
  pointerPad?: PointerPadConfig;
}

export interface PowerButtonConfig {
  position: 'left' | 'middle' | 'right';
  action: ProcessedAction;
  buttonType: 'power-off' | 'power-on' | 'power-toggle' | 'zone2-power';
}

export interface DropdownConfig {
  type: 'inputs' | 'apps';
  populationMethod: 'api' | 'commands'; // fetch options at runtime vs inline in the manifest
  // Canonical dispatch tuple (UI-9): selecting an option POSTs
  // /devices/{target}/canonical {capability, action, params: {[canonicalParam]: optionId}}.
  // Option ids are canonical values for BOTH population methods.
  canonicalCapability?: string;
  canonicalAction?: string;
  canonicalParam?: string;
  sourceDeviceId?: string; // scenario-inherited: which device to fetch/select against (the role device)
  options: DropdownOption[];
  loading: boolean;
  empty: boolean;
}

export interface DropdownOption {
  id: string;
  displayName: string;
  description?: string;
}

export interface PlaybackConfig {
  actions: ProcessedAction[];
  layout: 'horizontal' | 'cluster';
}

export interface TracksConfig {
  actions: ProcessedAction[];
  layout: 'horizontal' | 'vertical';
}

export interface VolumeSliderConfig {
  action: ProcessedAction;
  muteAction?: ProcessedAction;
  orientation: 'vertical';
  showValue: boolean;
  zone?: number;
  valueField?: string; // serialized device-state field holding the current level (e.g. 'zone2_volume') — Layer 3
  valueParam?: string; // native param the level value is sent under (e.g. 'volume' for Auralic, else 'level') — Layer 3
}

export interface VolumeButtonConfig {
  upAction?: ProcessedAction;
  downAction?: ProcessedAction;
  muteAction?: ProcessedAction;
  zone?: number;
}

export interface NavigationClusterConfig {
  upAction?: ProcessedAction;
  downAction?: ProcessedAction;
  leftAction?: ProcessedAction;
  rightAction?: ProcessedAction;
  okAction?: ProcessedAction;
  aux1Action?: ProcessedAction;
  aux2Action?: ProcessedAction;
  aux3Action?: ProcessedAction;
  aux4Action?: ProcessedAction;
}

export interface PointerPadConfig {
  moveAction: ProcessedAction;
  clickAction?: ProcessedAction;
  dragAction?: ProcessedAction;
  scrollAction?: ProcessedAction;
}

export interface ZoneLayoutConfig {
  priority?: number; // For volume zone priority system
  columns?: number;
  spacing?: 'compact' | 'normal' | 'spacious';
  alignment?: 'left' | 'center' | 'right';
  orientation?: 'horizontal' | 'vertical';
}

// Remote Control Device Structure - replaces DeviceStructure for remote layout
export interface ManualInstructions {
  startup: string[];
  shutdown: string[];
}

export interface RemoteDeviceStructure {
  deviceId: string;
  deviceName: string;
  deviceClass: string;
  remoteZones: RemoteZone[];
  stateInterface: import('./ProcessedDevice').StateDefinition;
  actionHandlers: import('./ProcessedDevice').ActionHandler[];
  manualInstructions?: ManualInstructions; // scenario-only: static notes rendered at the remote bottom
}

// (The legacy group-name-based ZoneDetectionConfig / DEFAULT_ZONE_DETECTION was removed at the
// Layer-3 cutover — zones are derived server-side from capability domains, not group-name matching.) 