import React from 'react';
import { cn } from '../../lib/utils';

interface CustomIconProps {
  icon: React.ComponentType<React.SVGProps<SVGSVGElement>>;
  size?: 'sm' | 'md' | 'lg';
  className?: string;
}

const sizeClasses = {
  sm: 'w-3 h-3',
  md: 'w-4 h-4', 
  lg: 'w-5 h-5'
};

export function CustomIcon({ icon: IconComponent, size = 'md', className }: CustomIconProps) {
  return (
    <IconComponent 
      className={cn(sizeClasses[size], className)}
      width={size === 'sm' ? 12 : size === 'md' ? 16 : 20}
      height={size === 'sm' ? 12 : size === 'md' ? 16 : 20}
    />
  );
} 