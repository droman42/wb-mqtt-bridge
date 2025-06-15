import React from 'react';
import { Icon } from './icons';
import { Button } from './ui/button';
import { cn } from '../lib/utils';

interface NavClusterProps {
  onUp?: () => void;
  onDown?: () => void;
  onLeft?: () => void;
  onRight?: () => void;
  onOk?: () => void;
  onAux1?: () => void;
  onAux2?: () => void;
  onAux3?: () => void;
  onAux4?: () => void;
  className?: string;
}

function NavCluster({
  onUp,
  onDown,
  onLeft,
  onRight,
  onOk,
  onAux1,
  onAux2,
  onAux3,
  onAux4,
  className
}: NavClusterProps) {
  return (
    <div className={cn("grid grid-cols-3 gap-2 w-48 h-48", className)}>
      {/* Top Row */}
      <Button 
        variant="outline" 
        size="icon"
        onClick={onAux1}
        className="h-14 w-14"
        disabled={!onAux1}
      >
        <span className="text-xs">AUX1</span>
      </Button>
      
      <Button 
        variant="outline" 
        size="icon"
        onClick={onUp}
        className="h-14 w-14"
        disabled={!onUp}
      >
        <Icon library="material" name="KeyboardArrowUp" size="lg" fallback="arrow-up" className="h-6 w-6" />
      </Button>
      
      <Button 
        variant="outline" 
        size="icon"
        onClick={onAux2}
        className="h-14 w-14"
        disabled={!onAux2}
      >
        <span className="text-xs">AUX2</span>
      </Button>

      {/* Middle Row */}
      <Button 
        variant="outline" 
        size="icon"
        onClick={onLeft}
        className="h-14 w-14"
        disabled={!onLeft}
      >
        <Icon library="material" name="KeyboardArrowLeft" size="lg" fallback="arrow-left" className="h-6 w-6" />
      </Button>
      
      <Button 
        variant="default" 
        size="icon"
        onClick={onOk}
        className="h-14 w-14"
        disabled={!onOk}
      >
        <Icon library="material" name="Check" size="lg" fallback="check" className="h-6 w-6" />
      </Button>
      
      <Button 
        variant="outline" 
        size="icon"
        onClick={onRight}
        className="h-14 w-14"
        disabled={!onRight}
      >
        <Icon library="material" name="KeyboardArrowRight" size="lg" fallback="arrow-right" className="h-6 w-6" />
      </Button>

      {/* Bottom Row */}
      <Button 
        variant="outline" 
        size="icon"
        onClick={onAux3}
        className="h-14 w-14"
        disabled={!onAux3}
      >
        <span className="text-xs">AUX3</span>
      </Button>
      
      <Button 
        variant="outline" 
        size="icon"
        onClick={onDown}
        className="h-14 w-14"
        disabled={!onDown}
      >
        <Icon library="material" name="KeyboardArrowDown" size="lg" fallback="arrow-down" className="h-6 w-6" />
      </Button>
      
      <Button 
        variant="outline" 
        size="icon"
        onClick={onAux4}
        className="h-14 w-14"
        disabled={!onAux4}
      >
        <span className="text-xs">AUX4</span>
      </Button>
    </div>
  );
}

export default NavCluster; 