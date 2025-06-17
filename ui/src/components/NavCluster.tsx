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
    <div className={cn("grid grid-cols-3 gap-2 w-48 h-48 p-3 rounded-lg bg-white/03", className)}>
      {/* Top Row */}
      <Button 
        variant="ghost" 
        size="icon"
        onClick={onAux1}
        className="h-14 w-14 bg-transparent border border-white/30 text-white hover:bg-white/10 hover:border-white/50 transition-all duration-200"
        disabled={!onAux1}
        title={aux1Action?.displayName || 'Home'}
      >
        {aux1Action ? (
          <Icon 
            library={aux1Action.icon.iconLibrary as 'material'} 
            name={aux1Action.icon.iconName} 
            fallback={aux1Action.icon.fallbackIcon} 
            size="lg"
            className="!w-8 !h-8 text-white" 
          />
        ) : (
          <Icon library="material" name="Home" fallback="home" size="lg" className="!w-8 !h-8 text-white" />
        )}
      </Button>
      
      <Button 
        variant="ghost" 
        size="icon"
        onClick={onUp}
        className="h-14 w-14 bg-transparent border border-white/30 text-white hover:bg-white/10 hover:border-white/50 transition-all duration-200"
        disabled={!onUp}
      >
        <Icon library="material" name="KeyboardArrowUp" fallback="arrow-up" size="lg" className="!w-8 !h-8 text-white" />
      </Button>
      
      <Button 
        variant="ghost" 
        size="icon"
        onClick={onAux2}
        className="h-14 w-14 bg-transparent border border-white/30 text-white hover:bg-white/10 hover:border-white/50 transition-all duration-200"
        disabled={!onAux2}
        title={aux2Action?.displayName || 'Menu'}
      >
        {aux2Action ? (
          <Icon 
            library={aux2Action.icon.iconLibrary as 'material'} 
            name={aux2Action.icon.iconName} 
            fallback={aux2Action.icon.fallbackIcon} 
            size="lg"
            className="!w-8 !h-8 text-white" 
          />
        ) : (
          <Icon library="material" name="Menu" fallback="menu" size="lg" className="!w-8 !h-8 text-white" />
        )}
      </Button>

      {/* Middle Row */}
      <Button 
        variant="ghost" 
        size="icon"
        onClick={onLeft}
        className="h-14 w-14 bg-transparent border border-white/30 text-white hover:bg-white/10 hover:border-white/50 transition-all duration-200"
        disabled={!onLeft}
      >
        <Icon library="material" name="KeyboardArrowLeft" fallback="arrow-left" size="lg" className="!w-8 !h-8 text-white" />
      </Button>
      
      <Button 
        variant="ghost" 
        size="icon"
        onClick={onOk}
        className="h-14 w-14 bg-transparent border border-white/30 text-white hover:bg-white/10 hover:border-white/50 transition-all duration-200"
        disabled={!onOk}
      >
        <Icon library="material" name="Check" fallback="check" size="lg" className="!w-8 !h-8 text-white" />
      </Button>
      
      <Button 
        variant="ghost" 
        size="icon"
        onClick={onRight}
        className="h-14 w-14 bg-transparent border border-white/30 text-white hover:bg-white/10 hover:border-white/50 transition-all duration-200"
        disabled={!onRight}
      >
        <Icon library="material" name="KeyboardArrowRight" fallback="arrow-right" size="lg" className="!w-8 !h-8 text-white" />
      </Button>

      {/* Bottom Row */}
      <Button 
        variant="ghost" 
        size="icon"
        onClick={onAux3}
        className="h-14 w-14 bg-transparent border border-white/30 text-white hover:bg-white/10 hover:border-white/50 transition-all duration-200"
        disabled={!onAux3}
        title={aux3Action?.displayName || 'Back'}
      >
        {aux3Action ? (
          <Icon 
            library={aux3Action.icon.iconLibrary as 'material'} 
            name={aux3Action.icon.iconName} 
            fallback={aux3Action.icon.fallbackIcon} 
            size="lg"
            className="!w-8 !h-8 text-white" 
          />
        ) : (
          <Icon library="material" name="ArrowBack" fallback="back" size="lg" className="!w-8 !h-8 text-white" />
        )}
      </Button>
      
      <Button 
        variant="ghost" 
        size="icon"
        onClick={onDown}
        className="h-14 w-14 bg-transparent border border-white/30 text-white hover:bg-white/10 hover:border-white/50 transition-all duration-200"
        disabled={!onDown}
      >
        <Icon library="material" name="KeyboardArrowDown" fallback="arrow-down" size="lg" className="!w-8 !h-8 text-white" />
      </Button>
      
      <Button 
        variant="ghost" 
        size="icon"
        onClick={onAux4}
        className="h-14 w-14 bg-transparent border border-white/30 text-white hover:bg-white/10 hover:border-white/50 transition-all duration-200"
        disabled={!onAux4}
        title={aux4Action?.displayName || 'Exit'}
      >
        {aux4Action ? (
          <Icon 
            library={aux4Action.icon.iconLibrary as 'material'} 
            name={aux4Action.icon.iconName} 
            fallback={aux4Action.icon.fallbackIcon} 
            size="lg"
            className="!w-8 !h-8 text-white" 
          />
        ) : (
          <Icon library="material" name="ExitToApp" fallback="exit" size="lg" className="!w-8 !h-8 text-white" />
        )}
      </Button>
    </div>
  );
}

export default NavCluster; 