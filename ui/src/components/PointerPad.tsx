import React from 'react';
import { Icon } from './icons';

interface PointerPadProps {
  mode: 'relative' | 'absolute';
  sensitivity?: number;
  hintIcon?: string | false;
  onMove: (x: number, y: number) => void;
  /** Fired when the user taps the pad without dragging — i.e. a short, small-distance
   *  gesture. Threshold-tuned to a standard trackpad "tap = click" heuristic
   *  (≤ TAP_MAX_DURATION_MS and ≤ TAP_MAX_DISTANCE_PX). When omitted, the pad is
   *  move-only. */
  onClick?: () => void;
  className?: string;
}

// Tap-vs-pan thresholds. Calibrated for finger + mouse input on a typical trackpad
// surface. Mobile-platform conventions: most native pickers use ~10 px / ~300 ms.
const TAP_MAX_DURATION_MS = 250;
const TAP_MAX_DISTANCE_PX = 6;

function PointerPad({
  mode,
  sensitivity = 1,
  hintIcon,
  onMove,
  onClick,
  className
}: PointerPadProps) {
  const [isDragging, setIsDragging] = React.useState(false);
  const [lastPosition, setLastPosition] = React.useState({ x: 0, y: 0 });
  const padRef = React.useRef<HTMLDivElement>(null);
  // Tap-vs-pan tracking: record start time + start position on handleStart;
  // accumulate total movement on handleMove; in handleEnd, if the gesture stayed
  // under both thresholds, fire onClick instead of treating it as a (zero-effect) drag.
  const tapStartRef = React.useRef<{ time: number; x: number; y: number } | null>(null);
  const tapMovedDistanceRef = React.useRef<number>(0);

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
    // Seed tap detection: record press start time + position, reset accumulated motion.
    tapStartRef.current = { time: Date.now(), x: pos.x, y: pos.y };
    tapMovedDistanceRef.current = 0;
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

    // Accumulate total distance from press-start for tap detection. We compare against
    // the START position (not the previous frame) so a slow drift past the threshold
    // disqualifies the gesture as a tap, even if no individual frame moved far.
    if (tapStartRef.current) {
      const dx = pos.x - tapStartRef.current.x;
      const dy = pos.y - tapStartRef.current.y;
      tapMovedDistanceRef.current = Math.hypot(dx, dy);
    }
  };

  const handleEnd = () => {
    setIsDragging(false);
    // Tap detection: short + small-movement gesture → onClick. Anything longer or
    // wider is a drag (the move events already fired during handleMove; no click).
    if (onClick && tapStartRef.current) {
      const duration = Date.now() - tapStartRef.current.time;
      const distance = tapMovedDistanceRef.current;
      if (duration <= TAP_MAX_DURATION_MS && distance <= TAP_MAX_DISTANCE_PX) {
        onClick();
      }
    }
    tapStartRef.current = null;
    tapMovedDistanceRef.current = 0;
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
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isDragging, lastPosition]);

  return (
    <div
      ref={padRef}
      className={`
        w-full h-full bg-secondary rounded-lg border-2 border-dashed border-border
        flex items-center justify-center cursor-pointer select-none
        transition-colors duration-200
        ${isDragging ? 'bg-primary/10 border-primary' : 'hover:bg-secondary/80'}
        ${className}
      `}
      onMouseDown={handleStart}
      onTouchStart={handleStart}
    >
      {hintIcon !== false && (
        <div className="flex flex-col items-center space-y-2 text-muted-foreground">
          <Icon library="material" name="PanTool" size="lg" fallback="hand" className="h-8 w-8" />
          <span className="text-sm">
            {mode === 'relative' ? 'Drag to move cursor' : 'Touch to position'}
          </span>
        </div>
      )}
    </div>
  );
}

export default PointerPad; 