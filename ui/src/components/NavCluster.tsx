import React from 'react';
import { Icon } from './icons';
import { Button } from './ui/button';
import { cn } from '../lib/utils';

interface AuxiliaryAction {
  actionName: string;
  displayName: string;
  description: string;
  icon: {
    iconLibrary: string;
    iconName: string;
    fallbackIcon: string;
  };
}

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
  aux1Action?: AuxiliaryAction;
  aux2Action?: AuxiliaryAction;
  aux3Action?: AuxiliaryAction;
  aux4Action?: AuxiliaryAction;
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
  aux1Action,
  aux2Action,
  aux3Action,
  aux4Action,
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
        title={aux1Action?.displayName || 'Home'}
      >
        {aux1Action ? (
          <Icon 
            library={aux1Action.icon.iconLibrary as 'material'} 
            name={aux1Action.icon.iconName} 
            fallback={aux1Action.icon.fallbackIcon} 
            size="lg" 
            className="h-6 w-6" 
          />
        ) : (
          <Icon library="material" name="Home" size="lg" fallback="home" className="h-6 w-6" />
        )}
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
        title={aux2Action?.displayName || 'Menu'}
      >
        {aux2Action ? (
          <Icon 
            library={aux2Action.icon.iconLibrary as 'material'} 
            name={aux2Action.icon.iconName} 
            fallback={aux2Action.icon.fallbackIcon} 
            size="lg" 
            className="h-6 w-6" 
          />
        ) : (
          <Icon library="material" name="Menu" size="lg" fallback="menu" className="h-6 w-6" />
        )}
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
        title={aux3Action?.displayName || 'Back'}
      >
        {aux3Action ? (
          <Icon 
            library={aux3Action.icon.iconLibrary as 'material'} 
            name={aux3Action.icon.iconName} 
            fallback={aux3Action.icon.fallbackIcon} 
            size="lg" 
            className="h-6 w-6" 
          />
        ) : (
          <Icon library="material" name="ArrowBack" size="lg" fallback="back" className="h-6 w-6" />
        )}
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
        title={aux4Action?.displayName || 'Exit'}
      >
        {aux4Action ? (
          <Icon 
            library={aux4Action.icon.iconLibrary as 'material'} 
            name={aux4Action.icon.iconName} 
            fallback={aux4Action.icon.fallbackIcon} 
            size="lg" 
            className="h-6 w-6" 
          />
        ) : (
          <Icon library="material" name="ExitToApp" size="lg" fallback="exit" className="h-6 w-6" />
        )}
      </Button>
    </div>
  );
}

export default NavCluster; 