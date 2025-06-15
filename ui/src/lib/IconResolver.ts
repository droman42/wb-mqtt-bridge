import type { ActionIcon } from '../types/ProcessedDevice';

export class IconResolver {
  private iconMappings: Record<string, { material: string; custom: string; fallback: string }> = {
    // Basic navigation
    power: { material: 'PowerSettingsNew', custom: '', fallback: 'power' },
    up: { material: 'KeyboardArrowUp', custom: '', fallback: 'arrow-up' },
    down: { material: 'KeyboardArrowDown', custom: '', fallback: 'arrow-down' },
    left: { material: 'KeyboardArrowLeft', custom: '', fallback: 'arrow-left' },
    right: { material: 'KeyboardArrowRight', custom: '', fallback: 'arrow-right' },
    ok: { material: 'Check', custom: '', fallback: 'check' },
    enter: { material: 'Check', custom: '', fallback: 'check' },
    select: { material: 'Check', custom: '', fallback: 'select' },
    menu: { material: 'Menu', custom: '', fallback: 'menu' },
    back: { material: 'Undo', custom: '', fallback: 'back' },
    home: { material: 'Home', custom: '', fallback: 'home' },
    
    // Media controls
    play: { material: 'PlayArrow', custom: '', fallback: 'play' },
    pause: { material: 'Pause', custom: '', fallback: 'pause' },
    stop: { material: 'Stop', custom: '', fallback: 'stop' },
    'play-pause': { material: '', custom: 'play-pause', fallback: 'play' },
    'playpause': { material: '', custom: 'play-pause', fallback: 'play' },
    next: { material: 'SkipNext', custom: '', fallback: 'next' },
    previous: { material: 'SkipPrevious', custom: '', fallback: 'previous' },
    rewind: { material: 'FastRewind', custom: '', fallback: 'rewind' },
    fastforward: { material: 'FastForward', custom: '', fallback: 'fast-forward' },
    tray: { material: 'Eject', custom: '', fallback: 'tray' },
    trayopen: { material: '', custom: 'tray-open', fallback: 'tray-open' },
    trayclose: { material: '', custom: 'tray-close', fallback: 'tray-close' },
    eject: { material: 'Eject', custom: '', fallback: 'eject' },
    
    // Audio controls
    volume: { material: 'VolumeUp', custom: '', fallback: 'volume' },
    volumeup: { material: 'VolumeUp', custom: '', fallback: 'volume-up' },
    volumedown: { material: 'VolumeDown', custom: '', fallback: 'volume-down' },
    mute: { material: 'VolumeOff', custom: '', fallback: 'mute' },
    
    // TV/Display controls
    tv: { material: 'Tv', custom: '', fallback: 'tv' },
    input: { material: 'Input', custom: '', fallback: 'input' },
    channel: { material: 'Tag', custom: '', fallback: 'channel' },
    audio: { material: 'Language', custom: '', fallback: 'audio' },
    subtitles: { material: 'Subtitles', custom: '', fallback: 'subtitles' },
    
    // Smart features
    siri: { material: 'Mic', custom: '', fallback: 'microphone' },
    voice: { material: 'Mic', custom: '', fallback: 'microphone' },
    airplay: { material: 'Cast', custom: '', fallback: 'wifi' },
    app: { material: 'Apps', custom: '', fallback: 'apps' },
    
    // Kitchen hood controls
    fan: { material: '', custom: 'fan', fallback: 'fan' },
    speed: { material: 'Speed', custom: '', fallback: 'speed' },
    light: { material: 'Lightbulb', custom: '', fallback: 'light' },
    timer: { material: 'Timer', custom: '', fallback: 'timer' },
    filter: { material: 'FilterAlt', custom: '', fallback: 'filter' },
    turbo: { material: 'FlashOn', custom: '', fallback: 'turbo' },
    
    // Audio processor controls
    bass: { material: 'GraphicEq', custom: '', fallback: 'bass' },
    treble: { material: 'GraphicEq', custom: '', fallback: 'treble' },
    balance: { material: 'Tune', custom: '', fallback: 'balance' },
    eq: { material: 'Equalizer', custom: '', fallback: 'equalizer' },
    zone: { material: 'Place', custom: '', fallback: 'zone' },
    
    // Pointer/cursor controls
    cursor: { material: 'CropFree', custom: '', fallback: 'cursor' },
    click: { material: 'TouchApp', custom: '', fallback: 'click' },
    drag: { material: 'PanTool', custom: '', fallback: 'drag' },
    scroll: { material: 'UnfoldMore', custom: '', fallback: 'scroll' },
    
    // General controls
    info: { material: 'Info', custom: '', fallback: 'info' },
    settings: { material: 'Settings', custom: '', fallback: 'settings' },
    mode: { material: 'Tune', custom: '', fallback: 'mode' },
    exit: { material: 'Close', custom: '', fallback: 'exit' },
    guide: { material: 'MenuBook', custom: '', fallback: 'guide' },
    
    // Numbers (for remote controls)
    '0': { material: '', custom: '0', fallback: '0' },
    '1': { material: '', custom: '1', fallback: '1' },
    '2': { material: '', custom: '2', fallback: '2' },
    '3': { material: '', custom: '3', fallback: '3' },
    '4': { material: '', custom: '4', fallback: '4' },
    '5': { material: '', custom: '5', fallback: '5' },
    '6': { material: '', custom: '6', fallback: '6' },
    
    // Aspect ratio controls
    'ratio-16-9': { material: '', custom: 'aspect-16-9', fallback: 'aspect-ratio' },
    'ratio169': { material: '', custom: 'aspect-16-9', fallback: 'aspect-ratio' },
    'ratio-4-3': { material: '', custom: 'aspect-4-3', fallback: 'aspect-ratio' },
    'ratio43': { material: '', custom: 'aspect-4-3', fallback: 'aspect-ratio' },
    'letterbox': { material: '', custom: 'letterbox', fallback: 'aspect-ratio' },
    
    // Additional common controls
    record: { material: 'FiberManualRecord', custom: '', fallback: 'record' },
    shuffle: { material: 'Shuffle', custom: '', fallback: 'shuffle' },
    repeat: { material: 'Repeat', custom: '', fallback: 'repeat' },
    bluetooth: { material: 'Bluetooth', custom: '', fallback: 'bluetooth' },
    wifi: { material: 'Wifi', custom: '', fallback: 'wifi' },
    usb: { material: 'Usb', custom: '', fallback: 'usb' }
  };
  
  selectIconForAction(actionName: string): ActionIcon {
    const cleanName = this.cleanActionName(actionName);
    const mapping = this.findBestMapping(cleanName);
    
    if (mapping) {
      // Prefer custom icon if available
      if (mapping.custom) {
        return {
          iconLibrary: 'custom',
          iconName: mapping.custom,
          iconVariant: 'outlined',
          fallbackIcon: mapping.fallback,
          confidence: 0.9
        };
      }
      
      // Otherwise use Material Design icon
      if (mapping.material) {
        return {
          iconLibrary: 'material',
          iconName: mapping.material,
          iconVariant: 'outlined',
          fallbackIcon: mapping.fallback,
          confidence: 0.9
        };
      }
    }
    
    // Fallback for unknown actions
    return {
      iconLibrary: 'material',
      iconName: 'Help',
      iconVariant: 'outlined', 
      fallbackIcon: 'command',
      confidence: 0.3
    };
  }
  
  selectMaterialIconForAction(actionName: string): ActionIcon {
    const cleanName = this.cleanActionName(actionName);
    const mapping = this.findBestMapping(cleanName);
    
    if (mapping && mapping.material) {
      return {
        iconLibrary: 'material',
        iconName: mapping.material,
        iconVariant: 'outlined',
        fallbackIcon: mapping.fallback,
        confidence: 0.9
      };
    }
    
    // Fallback for unknown actions
    return {
      iconLibrary: 'material',
      iconName: 'Help',
      iconVariant: 'outlined', 
      fallbackIcon: 'command',
      confidence: 0.3
    };
  }
  
  selectIconForActionWithLibrary(actionName: string, iconLibrary: 'material' | 'custom' = 'material'): ActionIcon {
    return iconLibrary === 'custom' 
      ? this.selectCustomIconForAction(actionName)
      : this.selectMaterialIconForAction(actionName);
  }
  
  selectCustomIconForAction(actionName: string): ActionIcon {
    const cleanName = this.cleanActionName(actionName);
    const mapping = this.findBestMapping(cleanName);
    
    if (mapping && mapping.custom) {
      return {
        iconLibrary: 'custom',
        iconName: mapping.custom,
        iconVariant: 'outlined',
        fallbackIcon: mapping.fallback,
        confidence: 0.9
      };
    }
    
    // Fallback to material design if no custom icon available
    return this.selectMaterialIconForAction(actionName);
  }
  
  private cleanActionName(actionName: string): string {
    return actionName.toLowerCase().replace(/[_-]/g, '').replace(/\s+/g, '');
  }
  
  private findBestMapping(cleanName: string): { material: string; custom: string; fallback: string } | null {
    // Direct match
    if (this.iconMappings[cleanName]) {
      return this.iconMappings[cleanName];
    }
    
    // Partial match - check if any mapping key is contained in the action name
    for (const [key, mapping] of Object.entries(this.iconMappings)) {
      if (cleanName.includes(key) || key.includes(cleanName)) {
        return mapping;
      }
    }
    
    return null;
  }
} 