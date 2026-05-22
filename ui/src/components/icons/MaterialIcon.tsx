import React from 'react';
import { cn } from '../../lib/utils';

interface MaterialIconProps {
  icon: React.ComponentType<any>;
  size?: 'sm' | 'md' | 'lg';
  className?: string;
}

const sizeClasses = {
  sm: 'w-3 h-3',
  md: 'w-4 h-4', 
  lg: 'w-5 h-5'
};

export function MaterialIcon({ icon: IconComponent, size = 'md', className }: MaterialIconProps) {
  return (
    <IconComponent 
      className={cn(sizeClasses[size], className)}
      style={{ 
        fontSize: size === 'sm' ? '12px' : size === 'md' ? '16px' : '20px' 
      }}
    />
  );
} 