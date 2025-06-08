import React from 'react';
import * as Icons from '@heroicons/react/24/solid';
import * as LucideIcons from 'lucide-react';
import { debounce } from '../lib/utils';
import { runtimeConfig } from '../config/runtime';

interface SliderControlProps {
  id: string;
  min: number;
  max: number;
  step?: number;
  value: number;
  icon?: string;
  ticks?: number[];
  onChange: (value: number) => void;
  className?: string;
}

function SliderControl({
  id,
  min,
  max,
  step = 1,
  value,
  icon,
  ticks,
  onChange,
  className
}: SliderControlProps) {
  const [localValue, setLocalValue] = React.useState(value);

  // Debounced onChange to avoid too many API calls
  const debouncedOnChange = React.useMemo(
    () => debounce(onChange, runtimeConfig.debounceDelaySec * 1000),
    [onChange]
  );

  React.useEffect(() => {
    setLocalValue(value);
  }, [value]);

  const handleChange = (newValue: number) => {
    setLocalValue(newValue);
    debouncedOnChange(newValue);
  };

  const renderIcon = () => {
    if (!icon) return null;

    if (icon.startsWith('lucide:')) {
      const iconName = icon.replace('lucide:', '');
      const LucideIcon = (LucideIcons as any)[iconName];
      return LucideIcon ? <LucideIcon className="h-5 w-5" /> : null;
    }

    // Heroicon
    const HeroIcon = (Icons as any)[icon];
    return HeroIcon ? <HeroIcon className="h-5 w-5" /> : null;
  };

  const percentage = ((localValue - min) / (max - min)) * 100;

  return (
    <div className={`space-y-2 ${className}`}>
      <div className="flex items-center space-x-2">
        {renderIcon()}
        <span className="text-sm font-medium">{id}</span>
        <span className="text-sm text-muted-foreground ml-auto">{localValue}</span>
      </div>
      
      <div className="relative">
        <input
          type="range"
          min={min}
          max={max}
          step={step}
          value={localValue}
          onChange={(e) => handleChange(Number(e.target.value))}
          className="w-full h-2 bg-secondary rounded-lg appearance-none cursor-pointer slider"
          style={{
            background: `linear-gradient(to right, hsl(var(--primary)) 0%, hsl(var(--primary)) ${percentage}%, hsl(var(--secondary)) ${percentage}%, hsl(var(--secondary)) 100%)`
          }}
        />
        
        {/* Tick marks */}
        {ticks && (
          <div className="absolute top-3 left-0 right-0 flex justify-between px-1">
            {ticks.map((tick) => {
              const tickPercentage = ((tick - min) / (max - min)) * 100;
              return (
                <div
                  key={tick}
                  className="w-px h-2 bg-muted-foreground"
                  style={{ marginLeft: `${tickPercentage}%` }}
                />
              );
            })}
          </div>
        )}
      </div>
      
      <div className="flex justify-between text-xs text-muted-foreground">
        <span>{min}</span>
        <span>{max}</span>
      </div>
    </div>
  );
}

export default SliderControl; 