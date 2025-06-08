import type { ActionIcon } from '../types/ProcessedDevice';

export class IconResolver {
  private iconMappings: Record<string, { heroicons: string; lucide: string; fallback: string }> = {
    // Basic navigation
    power: { heroicons: 'PowerIcon', lucide: 'power', fallback: 'power' },
    up: { heroicons: 'ChevronUpIcon', lucide: 'chevron-up', fallback: 'arrow-up' },
    down: { heroicons: 'ChevronDownIcon', lucide: 'chevron-down', fallback: 'arrow-down' },
    left: { heroicons: 'ChevronLeftIcon', lucide: 'chevron-left', fallback: 'arrow-left' },
    right: { heroicons: 'ChevronRightIcon', lucide: 'chevron-right', fallback: 'arrow-right' },
    ok: { heroicons: 'CheckIcon', lucide: 'check', fallback: 'check' },
    enter: { heroicons: 'CheckIcon', lucide: 'check', fallback: 'check' },
    select: { heroicons: 'CheckIcon', lucide: 'check', fallback: 'select' },
    menu: { heroicons: 'Bars3Icon', lucide: 'menu', fallback: 'menu' },
    back: { heroicons: 'ArrowLeftIcon', lucide: 'arrow-left', fallback: 'back' },
    home: { heroicons: 'HomeIcon', lucide: 'home', fallback: 'home' },
    
    // Media controls
    play: { heroicons: 'PlayIcon', lucide: 'play', fallback: 'play' },
    pause: { heroicons: 'PauseIcon', lucide: 'pause', fallback: 'pause' },
    stop: { heroicons: 'StopIcon', lucide: 'square', fallback: 'stop' },
    next: { heroicons: 'ForwardIcon', lucide: 'skip-forward', fallback: 'next' },
    previous: { heroicons: 'BackwardIcon', lucide: 'skip-back', fallback: 'previous' },
    rewind: { heroicons: 'BackwardIcon', lucide: 'rewind', fallback: 'rewind' },
    fastforward: { heroicons: 'ForwardIcon', lucide: 'fast-forward', fallback: 'fast-forward' },
    
    // Audio controls
    volume: { heroicons: 'SpeakerWaveIcon', lucide: 'volume-2', fallback: 'volume' },
    volumeup: { heroicons: 'SpeakerWaveIcon', lucide: 'volume-2', fallback: 'volume-up' },
    volumedown: { heroicons: 'SpeakerWaveIcon', lucide: 'volume-1', fallback: 'volume-down' },
    mute: { heroicons: 'SpeakerXMarkIcon', lucide: 'volume-x', fallback: 'mute' },
    
    // TV/Display controls
    tv: { heroicons: 'TvIcon', lucide: 'tv', fallback: 'tv' },
    input: { heroicons: 'ArrowsRightLeftIcon', lucide: 'arrow-left-right', fallback: 'input' },
    channel: { heroicons: 'HashtagIcon', lucide: 'hash', fallback: 'channel' },
    
    // Smart features
    siri: { heroicons: 'MicrophoneIcon', lucide: 'mic', fallback: 'microphone' },
    voice: { heroicons: 'MicrophoneIcon', lucide: 'mic', fallback: 'microphone' },
    airplay: { heroicons: 'WifiIcon', lucide: 'wifi', fallback: 'wifi' },
    app: { heroicons: 'Squares2X2Icon', lucide: 'grid-3x3', fallback: 'apps' },
    
    // Kitchen hood controls
    fan: { heroicons: 'CubeTransparentIcon', lucide: 'fan', fallback: 'fan' },
    speed: { heroicons: 'ArrowTrendingUpIcon', lucide: 'trending-up', fallback: 'speed' },
    light: { heroicons: 'LightBulbIcon', lucide: 'lightbulb', fallback: 'light' },
    timer: { heroicons: 'ClockIcon', lucide: 'timer', fallback: 'timer' },
    filter: { heroicons: 'FunnelIcon', lucide: 'filter', fallback: 'filter' },
    turbo: { heroicons: 'BoltIcon', lucide: 'zap', fallback: 'turbo' },
    
    // Audio processor controls
    bass: { heroicons: 'SpeakerWaveIcon', lucide: 'volume-2', fallback: 'bass' },
    treble: { heroicons: 'SpeakerWaveIcon', lucide: 'volume-2', fallback: 'treble' },
    balance: { heroicons: 'ArrowsRightLeftIcon', lucide: 'arrow-left-right', fallback: 'balance' },
    eq: { heroicons: 'AdjustmentsHorizontalIcon', lucide: 'sliders-horizontal', fallback: 'equalizer' },
    zone: { heroicons: 'MapIcon', lucide: 'map', fallback: 'zone' },
    
    // Pointer/cursor controls
    cursor: { heroicons: 'CursorArrowRaysIcon', lucide: 'mouse-pointer', fallback: 'cursor' },
    click: { heroicons: 'HandRaisedIcon', lucide: 'hand', fallback: 'click' },
    drag: { heroicons: 'HandRaisedIcon', lucide: 'hand', fallback: 'drag' },
    scroll: { heroicons: 'ArrowsUpDownIcon', lucide: 'arrows-up-down', fallback: 'scroll' },
    
    // General controls
    info: { heroicons: 'InformationCircleIcon', lucide: 'info', fallback: 'info' },
    settings: { heroicons: 'Cog6ToothIcon', lucide: 'settings', fallback: 'settings' },
    mode: { heroicons: 'Cog6ToothIcon', lucide: 'settings', fallback: 'mode' },
    exit: { heroicons: 'XMarkIcon', lucide: 'x', fallback: 'exit' },
    guide: { heroicons: 'BookOpenIcon', lucide: 'book-open', fallback: 'guide' }
  };
  
  selectIconForAction(actionName: string): ActionIcon {
    const cleanName = this.cleanActionName(actionName);
    const mapping = this.findBestMapping(cleanName);
    
    if (mapping) {
      return {
        iconLibrary: 'heroicons',
        iconName: mapping.heroicons,
        iconVariant: 'outline',
        fallbackIcon: mapping.fallback,
        confidence: 0.9
      };
    }
    
    // Fallback for unknown actions
    return {
      iconLibrary: 'heroicons',
      iconName: 'CommandLineIcon',
      iconVariant: 'outline', 
      fallbackIcon: 'command',
      confidence: 0.3
    };
  }
  
  private cleanActionName(actionName: string): string {
    return actionName.toLowerCase().replace(/[_-]/g, '').replace(/\s+/g, '');
  }
  
  private findBestMapping(cleanName: string): { heroicons: string; lucide: string; fallback: string } | null {
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