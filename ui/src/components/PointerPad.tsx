import React from 'react';
import { HandRaisedIcon } from '@heroicons/react/24/solid';

interface PointerPadProps {
  mode: 'relative' | 'absolute';
  sensitivity?: number;
  hintIcon?: string | false;
  onMove: (x: number, y: number) => void;
  className?: string;
}

function PointerPad({
  mode,
  sensitivity = 1,
  hintIcon,
  onMove,
  className
}: PointerPadProps) {
  const [isDragging, setIsDragging] = React.useState(false);
  const [lastPosition, setLastPosition] = React.useState({ x: 0, y: 0 });
  const padRef = React.useRef<HTMLDivElement>(null);

  const getEventPosition = (e: React.MouseEvent | React.TouchEvent) => {
    if ('touches' in e) {
      return { x: e.touches[0].clientX, y: e.touches[0].clientY };
    }
    return { x: e.clientX, y: e.clientY };
  };

  const handleStart = (e: React.MouseEvent | React.TouchEvent) => {
    e.preventDefault();
    setIsDragging(true);
    const pos = getEventPosition(e);
    setLastPosition(pos);
  };

  const handleMove = (e: React.MouseEvent | React.TouchEvent) => {
    if (!isDragging) return;
    e.preventDefault();

    const pos = getEventPosition(e);
    
    if (mode === 'relative') {
      const deltaX = (pos.x - lastPosition.x) * sensitivity;
      const deltaY = (pos.y - lastPosition.y) * sensitivity;
      onMove(deltaX, deltaY);
      setLastPosition(pos);
    } else {
      // Absolute mode
      if (padRef.current) {
        const rect = padRef.current.getBoundingClientRect();
        const x = ((pos.x - rect.left) / rect.width) * 100;
        const y = ((pos.y - rect.top) / rect.height) * 100;
        onMove(Math.max(0, Math.min(100, x)), Math.max(0, Math.min(100, y)));
      }
    }
  };

  const handleEnd = () => {
    setIsDragging(false);
  };

  React.useEffect(() => {
    const handleMouseMove = (e: MouseEvent) => {
      if (isDragging) {
        handleMove(e as any);
      }
    };

    const handleMouseUp = () => {
      handleEnd();
    };

    const handleTouchMove = (e: TouchEvent) => {
      if (isDragging) {
        handleMove(e as any);
      }
    };

    const handleTouchEnd = () => {
      handleEnd();
    };

    if (isDragging) {
      document.addEventListener('mousemove', handleMouseMove);
      document.addEventListener('mouseup', handleMouseUp);
      document.addEventListener('touchmove', handleTouchMove);
      document.addEventListener('touchend', handleTouchEnd);
    }

    return () => {
      document.removeEventListener('mousemove', handleMouseMove);
      document.removeEventListener('mouseup', handleMouseUp);
      document.removeEventListener('touchmove', handleTouchMove);
      document.removeEventListener('touchend', handleTouchEnd);
    };
  }, [isDragging, lastPosition]);

  return (
    <div className={`space-y-2 ${className}`}>
      <div className="flex items-center space-x-2">
        <span className="text-sm font-medium">Pointer Pad</span>
        <span className="text-xs text-muted-foreground">({mode})</span>
      </div>
      
      <div
        ref={padRef}
        className={`
          w-full h-48 bg-secondary rounded-lg border-2 border-dashed border-border
          flex items-center justify-center cursor-pointer select-none
          transition-colors duration-200
          ${isDragging ? 'bg-primary/10 border-primary' : 'hover:bg-secondary/80'}
        `}
        onMouseDown={handleStart}
        onTouchStart={handleStart}
      >
        {hintIcon !== false && (
          <div className="flex flex-col items-center space-y-2 text-muted-foreground">
            <HandRaisedIcon className="h-8 w-8" />
            <span className="text-sm">
              {mode === 'relative' ? 'Drag to move cursor' : 'Touch to position'}
            </span>
          </div>
        )}
      </div>
    </div>
  );
}

export default PointerPad; 