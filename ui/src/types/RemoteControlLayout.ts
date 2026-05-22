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
  populationMethod: 'api' | 'commands'; // API call vs direct commands
  apiAction?: string; // e.g., 'get_available_inputs'
  setAction?: string; // e.g., 'set_input'
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
export interface RemoteDeviceStructure {
  deviceId: string;
  deviceName: string;
  deviceClass: string;
  remoteZones: RemoteZone[];
  stateInterface: import('./ProcessedDevice').StateDefinition;
  actionHandlers: import('./ProcessedDevice').ActionHandler[];
  specialCases?: DeviceSpecialCase[];
}

export interface DeviceSpecialCase {
  deviceClass: string;
  caseType: 'emotiva-xmc2-power' | 'wirenboard-ir-commands' | 'lg-tv-inputs-apps' | 'appletv-streaming' | 'kitchen-hood-controls' | 'auralic-streaming' | 'revox-tape-deck';
  configuration: Record<string, any>;
}

// Zone detection configuration
export interface ZoneDetectionConfig {
  // Power Zone Detection
  powerGroupNames: string[];
  powerActionNames: string[];
  
  // Media Stack Detection
  inputsGroupNames: string[];
  playbackGroupNames: string[];
  tracksGroupNames: string[];
  tracksActionNames: string[];
  
  // Volume Zone Detection
  volumeGroupNames: string[];
  volumeActionNames: string[];
  
  // Navigation Detection
  menuGroupNames: string[];
  navigationActionNames: string[];
  
  // Screen Zone Detection
  screenGroupNames: string[];
  screenActionNames: string[];
  
  // Apps Detection
  appsGroupNames: string[];
  appsActionNames: string[];
  
  // Pointer Detection
  pointerGroupNames: string[];
  pointerActionNames: string[];
}

// Default zone detection patterns
export const DEFAULT_ZONE_DETECTION: ZoneDetectionConfig = {
  powerGroupNames: ['power', 'power_control', 'main_power'],
  powerActionNames: ['power', 'power_on', 'power_off', 'power_toggle', 'zone2_power'],
  
  inputsGroupNames: ['inputs', 'input_selection', 'sources', 'input_control'],
  playbackGroupNames: ['playback', 'media_control', 'transport', 'player'],
  tracksGroupNames: ['tracks', 'track_control', 'navigation', 'track_nav'],
  tracksActionNames: ['audio', 'subtitles', 'language', 'track', 'subtitle', 'tray', 'eject'],
  
  volumeGroupNames: ['volume', 'volume_control', 'audio', 'sound'],
  volumeActionNames: ['volume', 'volume_up', 'volume_down', 'mute', 'set_volume'],
  
  menuGroupNames: ['menu', 'navigation', 'nav', 'menu_nav', 'ui_nav'],
  navigationActionNames: ['up', 'down', 'left', 'right', 'ok', 'enter', 'select', 'back', 'menu', 'home', 'settings', 'exit', 'menu_exit'],
  
  screenGroupNames: ['screen', 'display', 'video', 'picture'],
  screenActionNames: ['aspect', 'zoom', 'display_mode', 'picture_mode', 'screen', 'ratio', 'letterbox'],
  
  appsGroupNames: ['apps', 'applications', 'channels', 'streaming'],
  appsActionNames: ['launch_app', 'select_app', 'app', 'channel'],
  
  pointerGroupNames: ['pointer', 'cursor', 'mouse', 'trackpad'],
  pointerActionNames: ['move', 'click', 'drag', 'scroll', 'cursor', 'pointer_gesture', 'touch_at_position', 'gesture', 'touch']
}; 