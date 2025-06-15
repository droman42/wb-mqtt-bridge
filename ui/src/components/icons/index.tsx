import React from 'react';
import { MaterialIcon } from './MaterialIcon';
import { CustomIcon } from './CustomIcon';
import { cn } from '../../lib/utils';

// Material Design Icons imports
import * as MaterialIcons from '@mui/icons-material';

// Custom Icons imports
import { PlayPause } from './custom/PlayPause';
import { TrayOpen } from './custom/TrayOpen';
import { TrayClose } from './custom/TrayClose';
import { Number0 } from './custom/Number0';
import { Number1 } from './custom/Number1';
import { Number2 } from './custom/Number2';
import { Number3 } from './custom/Number3';
import { Number4 } from './custom/Number4';
import { Number5 } from './custom/Number5';
import { Number6 } from './custom/Number6';
import { Fan } from './custom/Fan';
import { AspectRatio } from './custom/AspectRatio';
import { Letterbox } from './custom/Letterbox';

interface IconProps {
  library: 'material' | 'custom' | 'fallback';
  name: string;
  size?: 'sm' | 'md' | 'lg';
  className?: string;
  fallback?: string;
}

// Custom icons registry
const customIcons = {
  'play-pause': PlayPause,
  'tray-open': TrayOpen,
  'tray-close': TrayClose,
  'number-0': Number0,
  'number-1': Number1,
  'number-2': Number2,
  'number-3': Number3,
  'number-4': Number4,
  'number-5': Number5,
  'number-6': Number6,
  'fan': Fan,
  // Aspect ratio icons
  'aspect-16-9': (props: React.SVGProps<SVGSVGElement>) => <AspectRatio ratio="16:9" {...props} />,
  'aspect-4-3': (props: React.SVGProps<SVGSVGElement>) => <AspectRatio ratio="4:3" {...props} />,
  'letterbox': Letterbox,
  // Legacy number aliases for backward compatibility
  '0': Number0,
  '1': Number1,
  '2': Number2,
  '3': Number3,
  '4': Number4,
  '5': Number5,
  '6': Number6,
} as const;

// Fallback icon mapping for common icons
const fallbackIcons = {
  power: MaterialIcons.Power,
  play: MaterialIcons.PlayArrow,
  pause: MaterialIcons.Pause,
  stop: MaterialIcons.Stop,
  home: MaterialIcons.Home,
  menu: MaterialIcons.Menu,
  settings: MaterialIcons.Settings,
  close: MaterialIcons.Close,
} as const;

export function Icon({ library, name, size = 'md', className, fallback }: IconProps) {
  // Handle Material Design icons
  if (library === 'material') {
    const MaterialIconComponent = (MaterialIcons as any)[name];
    if (MaterialIconComponent) {
      return <MaterialIcon icon={MaterialIconComponent} size={size} className={className} />;
    }
  }
  
  // Handle custom icons
  if (library === 'custom') {
    const CustomIconComponent = customIcons[name as keyof typeof customIcons];
    if (CustomIconComponent) {
      return <CustomIcon icon={CustomIconComponent} size={size} className={className} />;
    }
  }
  
  // Fallback handling
  if (library === 'fallback' || !library) {
    const FallbackIconComponent = fallbackIcons[fallback as keyof typeof fallbackIcons] || MaterialIcons.Help;
    return <MaterialIcon icon={FallbackIconComponent} size={size} className={className} />;
  }
  
  // Ultimate fallback - show a help icon
  return <MaterialIcon icon={MaterialIcons.Help} size={size} className={cn('opacity-50', className)} />;
}

// Export individual components for direct use if needed
export { MaterialIcon, CustomIcon };
export * from './custom/PlayPause';
export * from './custom/TrayOpen';
export * from './custom/TrayClose';
export * from './custom/Number0';
export * from './custom/Number1';
export * from './custom/Number2';
export * from './custom/Number3';
export * from './custom/Number4';
export * from './custom/Number5';
export * from './custom/Number6';
export * from './custom/Fan';
export * from './custom/AspectRatio';
export * from './custom/Letterbox'; 