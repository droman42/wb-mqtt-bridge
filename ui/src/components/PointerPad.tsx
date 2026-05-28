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
// Pointer move events stream at the browser's pointer rate (60-120+/sec). Dispatching a
// backend command per event floods the action path (and the service log). We accumulate
// movement and flush at most once per this interval — relative deltas SUM losslessly, so
// total displacement is preserved; only the dispatch cadence is capped (~16/sec at 60ms).
const MOVE_THROTTLE_MS = 60;

function PointerPad({
  mode,
  sensitivity = 1,
  hintIcon,
  onMove,
  onClick,
  className
}: PointerPadProps) {
  const [isDragging, setIsDragging] = React.useState(false);
  const padRef = React.useRef<HTMLDivElement>(null);

  // Last pointer position lives in a ref (not state): it updates on every move, and as
  // state it forced a re-render + a document-listener rebind every frame. As a ref the
  // drag produces zero re-renders, so the listeners bind once per drag.
  const lastPositionRef = React.useRef({ x: 0, y: 0 });

  // Tap-vs-pan tracking: record start time + position on handleStart; accumulate total
  // movement on handleMove; in handleEnd decide tap (onClick) vs pan.
  const tapStartRef = React.useRef<{ time: number; x: number; y: number } | null>(null);
  const tapMovedDistanceRef = React.useRef<number>(0);
  // Becomes true once the gesture passes the tap thresholds — only then do we start
  // dispatching moves, so a pure tap emits a click and ZERO move commands.
  const dragConfirmedRef = React.useRef(false);

  // Throttle buffers. relative: accumulated dx/dy (summed); absolute: latest x/y (last-wins).
  const pendingRelRef = React.useRef({ dx: 0, dy: 0, dirty: false });
  const pendingAbsRef = React.useRef<{ x: number; y: number } | null>(null);
  const lastFlushTimeRef = React.useRef(0);
  const flushTimerRef = React.useRef<ReturnType<typeof setTimeout> | null>(null);

  // Latest callbacks in refs: the document listeners are bound once per drag (the effect
  // depends only on isDragging now), so reading the live callback avoids invoking a stale
  // onMove/onClick if the parent re-renders mid-drag.
  const onMoveRef = React.useRef(onMove);
  const onClickRef = React.useRef(onClick);
  onMoveRef.current = onMove;
  onClickRef.current = onClick;

  const now = () => (typeof performance !== 'undefined' ? performance.now() : Date.now());

  const clearFlushTimer = () => {
    if (flushTimerRef.current !== null) {
      clearTimeout(flushTimerRef.current);
      flushTimerRef.current = null;
    }
  };

  const flush = () => {
    clearFlushTimer();
    lastFlushTimeRef.current = now();
    if (mode === 'relative') {
      const pending = pendingRelRef.current;
      if (!pending.dirty) return;
      pendingRelRef.current = { dx: 0, dy: 0, dirty: false };
      onMoveRef.current(pending.dx, pending.dy);
    } else {
      const abs = pendingAbsRef.current;
      if (!abs) return;
      pendingAbsRef.current = null;
      onMoveRef.current(abs.x, abs.y);
    }
  };

  // Leading + trailing throttle: flush immediately if the interval has elapsed, else
  // schedule a single trailing flush so the tail of a move burst still lands.
  const scheduleFlush = () => {
    const elapsed = now() - lastFlushTimeRef.current;
    if (elapsed >= MOVE_THROTTLE_MS) {
      flush();
    } else if (flushTimerRef.current === null) {
      flushTimerRef.current = setTimeout(flush, MOVE_THROTTLE_MS - elapsed);
    }
  };

  const resetGesture = () => {
    clearFlushTimer();
    pendingRelRef.current = { dx: 0, dy: 0, dirty: false };
    pendingAbsRef.current = null;
    dragConfirmedRef.current = false;
  };

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
    lastPositionRef.current = pos;
    // Seed tap detection: record press start time + position, reset accumulated motion.
    tapStartRef.current = { time: Date.now(), x: pos.x, y: pos.y };
    tapMovedDistanceRef.current = 0;
    // Reset throttle state. lastFlushTime=0 makes the first post-confirmation flush
    // immediate (leading edge).
    resetGesture();
    lastFlushTimeRef.current = 0;
  };

  const handleMove = (e: React.MouseEvent | React.TouchEvent) => {
    if (!isDragging) return;
    e.preventDefault();

    const pos = getEventPosition(e);

    // Accumulate total distance from the START position for tap detection (compared to
    // start, not the previous frame, so a slow drift past the threshold disqualifies a tap).
    if (tapStartRef.current) {
      const dx = pos.x - tapStartRef.current.x;
      const dy = pos.y - tapStartRef.current.y;
      tapMovedDistanceRef.current = Math.hypot(dx, dy);
      if (!dragConfirmedRef.current) {
        const duration = Date.now() - tapStartRef.current.time;
        if (tapMovedDistanceRef.current > TAP_MAX_DISTANCE_PX || duration > TAP_MAX_DURATION_MS) {
          dragConfirmedRef.current = true;
        }
      }
    }

    if (mode === 'relative') {
      const deltaX = (pos.x - lastPositionRef.current.x) * sensitivity;
      const deltaY = (pos.y - lastPositionRef.current.y) * sensitivity;
      lastPositionRef.current = pos;
      pendingRelRef.current.dx += deltaX;
      pendingRelRef.current.dy += deltaY;
      pendingRelRef.current.dirty = true;
    } else if (padRef.current) {
      const rect = padRef.current.getBoundingClientRect();
      const x = ((pos.x - rect.left) / rect.width) * 100;
      const y = ((pos.y - rect.top) / rect.height) * 100;
      pendingAbsRef.current = {
        x: Math.max(0, Math.min(100, x)),
        y: Math.max(0, Math.min(100, y)),
      };
    }

    // Only start streaming once we're sure it's a drag, not a tap (keeps taps move-free).
    if (dragConfirmedRef.current) {
      scheduleFlush();
    }
  };

  const handleEnd = () => {
    setIsDragging(false);
    // Tap detection: short + small-movement gesture → onClick (and discard any buffered
    // sub-threshold jitter). Otherwise it's a drag: flush the final accumulated movement
    // so the end position is exact.
    const tapStart = tapStartRef.current;
    const isTap = !!(
      onClickRef.current &&
      tapStart &&
      Date.now() - tapStart.time <= TAP_MAX_DURATION_MS &&
      tapMovedDistanceRef.current <= TAP_MAX_DISTANCE_PX
    );

    if (isTap) {
      resetGesture();
      onClickRef.current!();
    } else {
      flush();
    }

    tapStartRef.current = null;
    tapMovedDistanceRef.current = 0;
    dragConfirmedRef.current = false;
  };

  React.useEffect(() => {
    if (!isDragging) return;

    const handleMouseMove = (e: MouseEvent) => handleMove(e as any);
    const handleMouseUp = () => handleEnd();
    const handleTouchMove = (e: TouchEvent) => handleMove(e as any);
    const handleTouchEnd = () => handleEnd();

    document.addEventListener('mousemove', handleMouseMove);
    document.addEventListener('mouseup', handleMouseUp);
    document.addEventListener('touchmove', handleTouchMove);
    document.addEventListener('touchend', handleTouchEnd);

    return () => {
      document.removeEventListener('mousemove', handleMouseMove);
      document.removeEventListener('mouseup', handleMouseUp);
      document.removeEventListener('touchmove', handleTouchMove);
      document.removeEventListener('touchend', handleTouchEnd);
      clearFlushTimer();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isDragging]);

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
