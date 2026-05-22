import React, { useState } from 'react';
import { Icon } from '../icons';
import { Button } from './button';

interface CollapsibleSectionProps {
  title: string;
  children: React.ReactNode;
  defaultOpen?: boolean;
  className?: string;
  headerClassName?: string;
  contentClassName?: string;
}

export function CollapsibleSection({
  title,
  children,
  defaultOpen = true,
  className = '',
  headerClassName = '',
  contentClassName = ''
}: CollapsibleSectionProps) {
  const [isOpen, setIsOpen] = useState(defaultOpen);

  return (
    <div className={`space-y-3 ${className}`}>
      <Button
        variant="ghost"
        size="sm"
        onClick={() => setIsOpen(!isOpen)}
        className={`w-full justify-between p-2 h-auto hover:bg-muted/50 ${headerClassName}`}
      >
        <h3 className="font-medium text-sm text-muted-foreground uppercase tracking-wider text-left">
          {title}
        </h3>
        <Icon
          library="material"
          name={isOpen ? "ExpandLess" : "ExpandMore"}
          size="sm"
          fallback={isOpen ? "up" : "down"}
          className="h-4 w-4 text-muted-foreground"
        />
      </Button>
      
      {isOpen && (
        <div className={`space-y-2 ${contentClassName}`}>
          {children}
        </div>
      )}
    </div>
  );
} 