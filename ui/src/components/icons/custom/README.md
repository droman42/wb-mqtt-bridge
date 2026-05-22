# Custom SVG Icons

This directory contains custom SVG icons that provide better semantic representation than Material Design icons for specialized device controls.

## Available Custom Icons

### Media Controls
- **`PlayPause`** - Combined play/pause icon with pause bar on left and play triangle on right
- **`TrayOpen`** - Disc player with extended tray showing a disc
- **`TrayClose`** - Disc player with closed tray and disc visible through slot

### Remote Control Numbers
- **`Number0` - `Number6`** - Button-style number icons (0-6) for remote controls
- **`Number`** - Base component that renders any number in a button format

### Device Controls  
- **`Fan`** - Kitchen hood fan with rotating blades (4 curved blades around center hub)

### Display Controls
- **`AspectRatio`** - Generic aspect ratio button with configurable ratio (e.g., "16:9", "4:3")
  - Renders a rectangle with the correct proportions and ratio text inside
- **`Letterbox`** - Letterbox format icon showing a rectangle with black bars on top and bottom

## Usage

### Direct Import
```tsx
import { PlayPause, TrayOpen, Fan, AspectRatio, Letterbox } from '../components/icons';

<PlayPause className="w-6 h-6" />
<TrayOpen className="w-4 h-4" />
<Fan className="w-5 h-5" />
<AspectRatio ratio="16:9" className="w-6 h-6" />
<Letterbox className="w-6 h-6" />
```

### Via Icon Component
```tsx
import { Icon } from '../components/icons';

<Icon library="custom" name="play-pause" size="md" />
<Icon library="custom" name="tray-open" size="sm" />
<Icon library="custom" name="fan" size="lg" />
<Icon library="custom" name="aspect-16-9" size="md" />
<Icon library="custom" name="letterbox" size="md" />
<Icon library="custom" name="0" size="md" />
```

## Design Guidelines

All custom icons follow these principles:
- **24x24 viewBox** for consistency with Material Design
- **currentColor** for theme compatibility  
- **Semantic clarity** over generic representation
- **Consistent stroke widths** (0.5-1.5) and opacity levels
- **Device-specific context** where Material Design falls short

## Icon Registry

Custom icons are automatically registered in `src/components/icons/index.tsx`:

```tsx
const customIcons = {
  'play-pause': PlayPause,
  'tray-open': TrayOpen,
  'tray-close': TrayClose,
  'fan': Fan,
  'aspect-16-9': (props) => <AspectRatio ratio="16:9" {...props} />,
  'aspect-4-3': (props) => <AspectRatio ratio="4:3" {...props} />,
  'letterbox': Letterbox,
  '0': Number0,
  '1': Number1,
  // ... etc
} as const;
``` 