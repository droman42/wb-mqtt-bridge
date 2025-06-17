import React, { useState, useEffect } from 'react';
import { cn } from '../lib/utils';
import { Button } from './ui/button';
import NavCluster from './NavCluster';
import PointerPad from './PointerPad';
import { Icon } from './icons';
import type { RemoteZone, RemoteDeviceStructure, PowerButtonConfig, VolumeButtonConfig } from '../types/RemoteControlLayout';
import { useInputsData, useAppsData, useInputSelection, useAppLaunching } from '../hooks/useRemoteControlData';
import { usePowerManagement } from '../hooks/usePowerManagement';

// Power Zone - 3-button layout with EMotiva special case
const PowerZone = ({ zone, onAction, className, isDisabled = false }: { zone?: RemoteZone; onAction: (action: string, payload?: any) => void; className?: string; isDisabled?: boolean }) => {
  if (!zone?.content?.powerButtons || zone.isEmpty) {
    return (
      <div className={cn("zone-empty", className)}>
        Power Zone (Empty)
      </div>
    );
  }

  const { powerButtons } = zone.content;
  
  // Create 3-button layout (left, middle, right)
  const leftButton = powerButtons.find(btn => btn.position === 'left');
  const middleButton = powerButtons.find(btn => btn.position === 'middle');
  const rightButton = powerButtons.find(btn => btn.position === 'right');

  const handlePowerAction = (button: PowerButtonConfig) => {
    onAction(button.action.actionName, button.action.parameters || {});
  };



  return (
    <div className={cn("zone-power", className)}>
      {/* Left Position */}
      {leftButton ? (
        <Button
          variant="ghost"
          size="sm"
          onClick={() => handlePowerAction(leftButton)}
          disabled={isDisabled}
          className="h-8 bg-transparent border border-white/30 text-white hover:bg-white/10 hover:border-white/50 transition-all duration-200"
        >
          <Icon
            library={leftButton.action.icon.iconLibrary as 'material'}
            name={leftButton.action.icon.iconName}
            fallback={leftButton.action.icon.fallbackIcon}
            size="lg"
            className="w-4 h-4 text-white"
          />
        </Button>
      ) : (
        <div></div>
      )}

      {/* Middle Position */}
      {middleButton ? (
        <Button
          variant="ghost"
          size="sm"
          onClick={() => handlePowerAction(middleButton)}
          disabled={isDisabled}
          className="h-8 bg-transparent border border-white/30 text-white hover:bg-white/10 hover:border-white/50 transition-all duration-200"
        >
          <Icon
            library={middleButton.action.icon.iconLibrary as 'material'}
            name={middleButton.action.icon.iconName}
            fallback={middleButton.action.icon.fallbackIcon}
            size="lg"
            className="w-4 h-4 text-white"
          />
        </Button>
      ) : (
        <div></div>
      )}

      {/* Right Position */}
      {rightButton ? (
        <Button
          variant="ghost"
          size="sm"
          onClick={() => handlePowerAction(rightButton)}
          disabled={isDisabled}
          className="h-8 bg-transparent border border-white/30 text-white hover:bg-white/10 hover:border-white/50 transition-all duration-200"
        >
          <Icon
            library={rightButton.action.icon.iconLibrary as 'material'}
            name={rightButton.action.icon.iconName}
            fallback={rightButton.action.icon.fallbackIcon}
            size="lg"
            className="w-4 h-4 text-white"
          />
        </Button>
      ) : (
        <div></div>
      )}
    </div>
  );
};

// Media Stack Zone - INPUTS, PLAYBACK, TRACKS sections
const MediaStackZone = ({ zone, deviceStructure, onAction, className, isDisabled = false }: { 
  zone?: RemoteZone; 
  deviceStructure: RemoteDeviceStructure;
  onAction: (action: string, payload?: any) => void; 
  className?: string;
  isDisabled?: boolean;
}) => {
  // Use dynamic input data hooks
  const { inputs: dynamicInputs, loading: inputsLoading, error: inputsError } = useInputsData(deviceStructure);
  const { selectedInput, selectInput } = useInputSelection(deviceStructure);

  if (!zone?.content || zone.isEmpty) {
    return (
      <div className={cn("zone-empty", className)}>
        Media Stack (Empty)  
      </div>
    );
  }

  const { playbackSection, tracksSection, inputsDropdown } = zone.content;

  // Check if device has inputs capability (from zone configuration)
  const hasInputsCapability = !!inputsDropdown;

  const handleInputSelect = async (inputId: string) => {
    try {
      await selectInput(inputId);
    } catch (error) {
      console.error('Failed to select input:', error);
    }
  };

  const handlePlaybackAction = (action: any) => {
    onAction(action.actionName, action.parameters || {});
  };

  return (
    <div className={cn("zone-media-stack", className)}>
      {/* INPUTS Section - Always show if device has inputs capability */}
      {hasInputsCapability && (
        <div className="inputs-section media-stack-group">
          <span className="media-stack-legend">
            INPUTS {inputsLoading && "(Loading...)"}
          </span>
          <div className="media-stack-content">
            {inputsError && !inputsError.includes('powered off') ? (
              <div className="text-amber-400 text-xs mb-1">
                {inputsError === 'Device is disconnected' ? (
                  "Device is disconnected" 
                ) : inputsError === 'Loading device state...' ? (
                  "Loading device state..."
                ) : (
                  `Error loading inputs: ${inputsError}`
                )}
              </div>
            ) : null}
            <select
              value={selectedInput}
              onChange={(e) => handleInputSelect(e.target.value)}
              className="w-full px-2 py-1 text-xs bg-black/30 border border-white/20 rounded text-white"
              disabled={isDisabled || inputsLoading || !!(inputsError && (inputsError.includes('powered off') || inputsError.includes('disconnected')))}
            >
              <option value="">
                {inputsLoading ? "Loading inputs..." : 
                 inputsError && inputsError.includes('powered off') ? "Device powered off" :
                 inputsError && inputsError.includes('disconnected') ? "Device disconnected" :
                 inputsError && inputsError.includes('Loading device state') ? "Loading device state..." :
                 inputsError ? `Error: ${inputsError}` :
                 "Select Input..."}
              </option>
              {dynamicInputs.map((option) => (
                <option key={option.id} value={option.id}>
                  {option.displayName}
                </option>
              ))}
            </select>
          </div>
        </div>
      )}

      {/* PLAYBACK Section */}
      {playbackSection && playbackSection.actions.length > 0 && (
        <div className="playback-section media-stack-group">
          <span className="media-stack-legend">PLAYBACK</span>
          <div className="media-stack-content">
            <div className="flex gap-1 flex-wrap">
              {playbackSection.actions.map((action, index) => (
                <Button
                  key={index}
                  variant="ghost"
                  size="sm"
                  onClick={() => handlePlaybackAction(action)}
                  disabled={isDisabled}
                  className="h-10 px-2 flex-1 min-w-fit bg-transparent border border-white/30 text-white hover:bg-white/10 hover:border-white/50 transition-all duration-200"
                >
                  <Icon
                    library={action.icon.iconLibrary as 'material'}
                    name={action.icon.iconName}
                    fallback={action.icon.fallbackIcon}
                    size="lg"
                    className="w-5 h-5 text-white"
                  />
                </Button>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* TRACKS Section */}
      {tracksSection && tracksSection.actions.length > 0 && (
        <div className="tracks-section media-stack-group">
          <span className="media-stack-legend">TRACKS</span>
          <div className="media-stack-content">
            <div className="flex gap-1">
              {tracksSection.actions.map((action, index) => (
                <Button
                  key={index}
                  variant="ghost"
                  size="sm"
                  onClick={() => handlePlaybackAction(action)}
                  className="h-10 px-2 flex-1 bg-transparent border border-white/30 text-white hover:bg-white/10 hover:border-white/50 transition-all duration-200"
                >
                  <Icon
                    library={action.icon.iconLibrary as 'material'}
                    name={action.icon.iconName}
                    fallback={action.icon.fallbackIcon}
                    size="lg"
                    className="w-5 h-5 text-white"
                  />
                </Button>
              ))}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

// Screen Zone - Vertical button alignment
const ScreenZone = ({ zone, onAction, className }: { zone?: RemoteZone; onAction: (action: string, payload?: any) => void; className?: string }) => {
  if (!zone?.content?.screenActions || zone.isEmpty) {
    return (
      <div className={cn("zone-empty", className)}>
        Screen Zone (Empty)
      </div>
    );
  }

  const { screenActions } = zone.content;

  const handleScreenAction = (action: any) => {
    onAction(action.actionName, action.parameters || {});
  };

  return (
    <div className={cn("zone-screen", className)}>
      <div className="flex flex-col gap-2 items-center justify-center h-full">
        {screenActions.map((action, index) => (
          <Button
            key={index}
            variant="ghost"
            size="sm"
            onClick={() => handleScreenAction(action)}
            className="h-10 w-10 justify-center bg-transparent border border-white/30 text-white hover:bg-white/10 hover:border-white/50 transition-all duration-200"
          >
            <Icon
              library={action.icon.iconLibrary as 'material'}
              name={action.icon.iconName}
              fallback={action.icon.fallbackIcon}
              size="lg"
              className="w-6 h-6 text-white"
            />
          </Button>
        ))}
      </div>
    </div>
  );
};

// Volume Zone - Priority-based (slider vs buttons) with vertical orientation
const VolumeZone = ({ zone, onAction, className }: { zone?: RemoteZone; onAction: (action: string, payload?: any) => void; className?: string }) => {
  const [isDragging, setIsDragging] = useState(false);
  
  // Get volume range from device configuration (with fallback)
  const getVolumeRange = () => {
    if (zone?.content?.volumeSlider?.action?.parameters) {
      const rangeParam = zone.content.volumeSlider.action.parameters.find(p => p.type === 'range');
      if (rangeParam) {
        return {
          min: rangeParam.min ?? 0,
          max: rangeParam.max ?? 100,
          default: rangeParam.default ?? rangeParam.min ?? 0
        };
      }
    }
    return { min: 0, max: 100, default: 50 }; // Fallback to 0-100
  };

  const volumeRange = getVolumeRange();
  const [volume, setVolume] = useState(volumeRange.default);

  if (!zone?.content || zone.isEmpty) {
    return (
      <div className={cn("zone-empty", className)}>
        Volume Zone (Empty)
      </div>
    );
  }

  const { volumeSlider, volumeButtons } = zone.content;

  const handleVolumeSlider = (newVolume: number) => {
    setVolume(newVolume);
    if (volumeSlider?.action) {
      onAction(volumeSlider.action.actionName, { level: newVolume });
    }
  };

  const handleVolumeButton = (action: any) => {
    onAction(action.actionName, action.parameters || {});
  };

  const handleSliderInteraction = (e: React.MouseEvent | React.TouchEvent) => {
    const target = e.currentTarget;
    const rect = target.getBoundingClientRect();
    const clientY = 'touches' in e ? e.touches[0].clientY : e.clientY;
    const y = clientY - rect.top;
    const percentage = Math.max(0, Math.min(100, ((rect.height - y) / rect.height) * 100));
    
    // Convert percentage to actual volume value based on device range
    const volumeValue = volumeRange.min + (percentage / 100) * (volumeRange.max - volumeRange.min);
    
    // Calculate snap increment based on range (roughly 20 steps across the range)
    const rangeSize = volumeRange.max - volumeRange.min;
    const snapIncrement = Math.max(1, Math.round(rangeSize / 20));
    const snappedValue = Math.round(volumeValue / snapIncrement) * snapIncrement;
    
    handleVolumeSlider(Math.max(volumeRange.min, Math.min(volumeRange.max, snappedValue)));
  };

  const handleMouseDown = (e: React.MouseEvent) => {
    setIsDragging(true);
    handleSliderInteraction(e);

    const handleMouseMove = (event: MouseEvent) => {
      const target = e.currentTarget;
      const rect = target.getBoundingClientRect();
      const y = event.clientY - rect.top;
      const percentage = Math.max(0, Math.min(100, ((rect.height - y) / rect.height) * 100));
      
      // Convert percentage to actual volume value based on device range
      const volumeValue = volumeRange.min + (percentage / 100) * (volumeRange.max - volumeRange.min);
      
      // Calculate snap increment based on range
      const rangeSize = volumeRange.max - volumeRange.min;
      const snapIncrement = Math.max(1, Math.round(rangeSize / 20));
      const snappedValue = Math.round(volumeValue / snapIncrement) * snapIncrement;
      
      handleVolumeSlider(Math.max(volumeRange.min, Math.min(volumeRange.max, snappedValue)));
    };

    const handleMouseUp = () => {
      setIsDragging(false);
      document.removeEventListener('mousemove', handleMouseMove);
      document.removeEventListener('mouseup', handleMouseUp);
    };

    document.addEventListener('mousemove', handleMouseMove);
    document.addEventListener('mouseup', handleMouseUp);
  };

  // Priority 1: Slider + Mute
  if (volumeSlider) {
    // Calculate percentage for visual display (0-100%)
    const volumePercentage = ((volume - volumeRange.min) / (volumeRange.max - volumeRange.min)) * 100;
    
    // Calculate tick mark values based on device range
    const tickCount = 11; // Keep 11 ticks for visual consistency
    const tickValues = Array.from({ length: tickCount }, (_, i) => {
      return volumeRange.min + (i / (tickCount - 1)) * (volumeRange.max - volumeRange.min);
    });

    return (
      <div className={cn("zone-volume", className)}>
        <div className="flex flex-col items-center gap-2 h-full">
          {/* Volume Value Display - Show actual device value */}
          <div className="text-xs text-white/70">{Math.round(volume)}</div>
          
          {/* Thermometer-Style Vertical Slider */}
          <div className="flex-1 flex items-center justify-center">
            <div className="relative flex flex-col items-center">
              {/* Main Slider Container */}
              <div 
                className={`relative cursor-pointer select-none ${isDragging ? 'opacity-80' : ''}`}
                onMouseDown={handleMouseDown}
                onTouchStart={(e) => {
                  setIsDragging(true);
                  handleSliderInteraction(e);
                }}
                onTouchMove={handleSliderInteraction}
                onTouchEnd={() => setIsDragging(false)}
                style={{ height: '140px', width: '40px' }}
              >
                {/* Central Vertical Bar */}
                <div className="absolute left-1/2 transform -translate-x-1/2 w-1 h-full bg-white/60"></div>
                
                {/* Filled portion of the bar */}
                <div 
                  className="absolute left-1/2 transform -translate-x-1/2 w-1 bg-blue-400 transition-all duration-200 bottom-0"
                  style={{ height: `${volumePercentage}%` }}
                ></div>
                
                {/* Tick Marks */}
                {tickValues.map((tickValue, i) => {
                  const isActive = tickValue <= volume;
                  const isMajor = i % 2 === 0; // Major ticks at every other position
                  const tickLength = isMajor ? '8px' : '6px';
                  const position = `${100 - (i / (tickCount - 1)) * 100}%`;
                  
                  return (
                    <div key={i}>
                      {/* Left tick */}
                      <div
                        className={`absolute border-t transition-colors duration-200 ${
                          isActive ? 'border-blue-400' : 'border-white/40'
                        }`}
                        style={{
                          top: position,
                          left: `calc(50% - ${tickLength})`,
                          width: tickLength,
                          transform: 'translateY(-0.5px)'
                        }}
                      ></div>
                      
                      {/* Right tick */}
                      <div
                        className={`absolute border-t transition-colors duration-200 ${
                          isActive ? 'border-blue-400' : 'border-white/40'
                        }`}
                        style={{
                          top: position,
                          left: '50%',
                          width: tickLength,
                          transform: 'translateY(-0.5px)'
                        }}
                      ></div>
                      
                      {/* Volume level indicator numbers for major ticks */}
                      {isMajor && (
                        <div
                          className={`absolute text-xs transition-colors duration-200 ${
                            isActive ? 'text-blue-400' : 'text-white/50'
                          }`}
                          style={{
                            top: position,
                            left: 'calc(50% + 12px)',
                            transform: 'translateY(-6px)',
                            fontSize: '8px'
                          }}
                        >
                          {Math.round(tickValue)}
                        </div>
                      )}
                    </div>
                  );
                })}
                
                {/* Volume Level Indicator */}
                <div
                  className={`absolute w-3 h-0.5 bg-blue-500 shadow-sm transition-all duration-200 ${
                    isDragging ? 'scale-110' : ''
                  }`}
                  style={{
                    bottom: `calc(${volumePercentage}% - 1px)`,
                    left: '50%',
                    transform: 'translateX(-50%)'
                  }}
                ></div>
              </div>
            </div>
          </div>

          {/* Mute Button */}
          {volumeSlider.muteAction && (
            <Button
              variant="ghost"
              size="sm"
              onClick={() => handleVolumeButton(volumeSlider.muteAction)}
              className="h-8 w-12 bg-transparent border border-white/30 text-white hover:bg-white/10 hover:border-white/50 transition-all duration-200"
            >
              <Icon
                library={volumeSlider.muteAction.icon.iconLibrary as 'material'}
                name={volumeSlider.muteAction.icon.iconName}
                fallback={volumeSlider.muteAction.icon.fallbackIcon}
                size="lg"
                className="w-4 h-4 text-white"
              />
            </Button>
          )}
        </div>
      </div>
    );
  }

  // Priority 2: Volume Up/Down Buttons
  if (volumeButtons && volumeButtons.length > 0) {
    const buttons = volumeButtons[0] as VolumeButtonConfig;
    return (
      <div className={cn("zone-volume", className)}>
        <div className="flex flex-col gap-1 items-center">
          {/* Volume Up */}
          {buttons.upAction && (
            <Button
              variant="ghost"
              size="sm"
              onClick={() => handleVolumeButton(buttons.upAction)}
              className="h-10 w-12 bg-transparent border border-white/30 text-white hover:bg-white/10 hover:border-white/50 transition-all duration-200"
            >
              <Icon
                library={buttons.upAction.icon.iconLibrary as 'material'}
                name={buttons.upAction.icon.iconName}
                fallback={buttons.upAction.icon.fallbackIcon}
                size="lg"
                className="w-5 h-5 text-white"
              />
            </Button>
          )}

          {/* Volume Down */}
          {buttons.downAction && (
            <Button
              variant="ghost"
              size="sm"
              onClick={() => handleVolumeButton(buttons.downAction)}
              className="h-10 w-12 bg-transparent border border-white/30 text-white hover:bg-white/10 hover:border-white/50 transition-all duration-200"
            >
              <Icon
                library={buttons.downAction.icon.iconLibrary as 'material'}
                name={buttons.downAction.icon.iconName}
                fallback={buttons.downAction.icon.fallbackIcon}
                size="lg"
                className="w-5 h-5 text-white"
              />
            </Button>
          )}

          {/* Mute */}
          {buttons.muteAction && (
            <Button
              variant="ghost"
              size="sm"
              onClick={() => handleVolumeButton(buttons.muteAction)}
              className="h-10 w-12 bg-transparent border border-white/30 text-white hover:bg-white/10 hover:border-white/50 transition-all duration-200"
            >
              <Icon
                library={buttons.muteAction.icon.iconLibrary as 'material'}
                name={buttons.muteAction.icon.iconName}
                fallback={buttons.muteAction.icon.fallbackIcon}
                size="lg"
                className="w-5 h-5 text-white"
              />
            </Button>
          )}
        </div>
      </div>
    );
  }

  return (
    <div className={cn("zone-empty", className)}>
      Volume Zone (Empty)
    </div>
  );
};

// Apps Zone - Dropdown selector
const AppsZone = ({ zone, deviceStructure, className }: { 
  zone?: RemoteZone; 
  deviceStructure: RemoteDeviceStructure;
  className?: string 
}) => {
  // Use dynamic app data hooks
  const { apps: dynamicApps, loading: appsLoading, error: appsError } = useAppsData(deviceStructure);
  const { selectedApp, launchApp } = useAppLaunching(deviceStructure);

  // Show empty state if no apps available and not loading and no error
  if ((!zone?.content?.appsDropdown || zone?.isEmpty) && dynamicApps.length === 0 && !appsLoading && !appsError) {
    return (
      <div className={cn("zone-apps", className)}>
        <span className="zone-legend">APPS</span>
        <div className="zone-content zone-empty">
          Apps Zone (Empty)
        </div>
      </div>
    );
  }

  const handleAppSelect = async (appId: string) => {
    try {
      await launchApp(appId);
    } catch (error) {
      console.error('Failed to launch app:', error);
    }
  };

  return (
    <div className={cn("zone-apps", className)}>
      <span className="zone-legend">
        APPS {appsLoading && "(Loading...)"}
      </span>
      <div className="zone-content">
        {appsError && !appsError.includes('powered off') ? (
          <div className="text-amber-400 text-xs mb-1">
            {appsError === 'Device is disconnected' ? (
              "Device is disconnected" 
            ) : (
              `Error loading apps: ${appsError}`
            )}
          </div>
        ) : null}
        <select
          value={selectedApp}
          onChange={(e) => handleAppSelect(e.target.value)}
          className="w-full px-2 py-1 text-xs bg-black/30 border border-white/20 rounded text-white"
          disabled={appsLoading || !!(appsError && (appsError.includes('powered off') || appsError.includes('disconnected')))}
        >
          <option value="">
            {appsLoading ? "Loading apps..." : 
             appsError && appsError.includes('powered off') ? "Device powered off" :
             appsError && appsError.includes('disconnected') ? "Device disconnected" :
             "Select App..."}
          </option>
          {dynamicApps.map((option) => (
            <option key={option.id} value={option.id}>
              {option.displayName}
            </option>
          ))}
        </select>
      </div>
    </div>
  );
};

// Menu Navigation Zone - NavCluster integration with styling adjustments
const MenuZone = ({ zone, onAction, className }: { zone?: RemoteZone; onAction: (action: string, payload?: any) => void; className?: string }) => {
  if (!zone?.content?.navigationCluster) {
    return (
      <div className={cn("zone-empty", className)}>
        Navigation (Empty)
      </div>
    );
  }

  const { navigationCluster } = zone.content;

  const createHandler = (action: any) => {
    return action ? () => onAction(action.actionName, action.parameters || {}) : undefined;
  };

  return (
    <div className={cn("zone-menu", className)}>
      <NavCluster
        onUp={createHandler(navigationCluster.upAction)}
        onDown={createHandler(navigationCluster.downAction)}
        onLeft={createHandler(navigationCluster.leftAction)}
        onRight={createHandler(navigationCluster.rightAction)}
        onOk={createHandler(navigationCluster.okAction)}
        onAux1={createHandler(navigationCluster.aux1Action)}
        onAux2={createHandler(navigationCluster.aux2Action)}
        onAux3={createHandler(navigationCluster.aux3Action)}
        onAux4={createHandler(navigationCluster.aux4Action)}
        aux1Action={navigationCluster.aux1Action}
        aux2Action={navigationCluster.aux2Action}
        aux3Action={navigationCluster.aux3Action}
        aux4Action={navigationCluster.aux4Action}
        className="scale-75 transform"
      />
    </div>
  );
};

// Pointer Zone - PointerPad with lighter theme styling
const PointerZone = ({ zone, onAction, className }: { zone?: RemoteZone; onAction: (action: string, payload?: any) => void; className?: string }) => {
  if (!zone?.content?.pointerPad || zone?.isEmpty) {
    return (
      <div className={cn("zone-pointer", className)}>
        <span className="zone-legend">Pointer Pad</span>
        <div className="zone-content pointer-content zone-empty">
          Pointer Zone (Empty)
        </div>
      </div>
    );
  }

  const { pointerPad } = zone.content;

  const handleMove = (deltaX: number, deltaY: number) => {
    if (pointerPad.moveAction) {
      onAction(pointerPad.moveAction.actionName, { deltaX, deltaY });
    }
  };

  const _handleClick = () => {
    if (pointerPad.clickAction) {
      onAction(pointerPad.clickAction.actionName, {});
    }
  };

  return (
    <div className={cn("zone-pointer", className)}>
      <span className="zone-legend">Pointer Pad (relative)</span>
      <div className="zone-content pointer-content">
        <PointerPad
          mode="relative"
          onMove={handleMove}
          className="w-full h-full bg-white/10 border border-white/20 rounded-lg"
        />
      </div>
    </div>
  );
};

interface RemoteControlLayoutProps {
  deviceStructure: RemoteDeviceStructure;
  onAction: (actionName: string, payload?: any) => void;
  className?: string;
}

export function RemoteControlLayout({ 
  deviceStructure, 
  onAction, 
  className 
}: RemoteControlLayoutProps) {
  const { deviceName, remoteZones, deviceId } = deviceStructure;
  
  // Power management hook
  const { handlePowerOn, isControlDisabled } = usePowerManagement(deviceId);

  // Expose device structure to global context for DeviceStatePanel access
  useEffect(() => {
    if (typeof window !== 'undefined') {
      (window as any).currentDeviceStructure = deviceStructure;
    }
    
    // Cleanup when component unmounts or device changes
    return () => {
      if (typeof window !== 'undefined') {
        (window as any).currentDeviceStructure = null;
      }
    };
  }, [deviceStructure]);

  // Zone lookup for easier access
  const zones = remoteZones.reduce((acc, zone) => {
    acc[zone.zoneId] = zone;
    return acc;
  }, {} as Record<string, RemoteZone>);

  // Enhanced action handler with power-on integration
  const handleActionWithPowerManagement = async (actionName: string, payload?: any) => {
    // Check if this is a power-on action
    if (actionName === 'power_on') {
      try {
        await handlePowerOn(deviceStructure);
      } catch (error) {
        console.error('Power-on sequence failed:', error);
        // Error is already logged to log panel by power management hook
        return;
      }
    } else {
      // Regular action - just call the original handler
      onAction(actionName, payload);
    }
  };
  


      return (
      <div className={cn("flex justify-center w-full", className)}>
        {/* Remote Control Container */}
        <div className="remote-control-container" style={{contain: 'layout style'}}>
        {/* Device Name Header */}
        <div className="remote-header">
          <h1 className="text-lg font-bold text-white text-center tracking-wide">
            {deviceName}
          </h1>
        </div>

        {/* Zone Layout */}
        <div className="remote-zones">
          {/* Power Zone (①) - Show/Hide */}
          {zones.power && !zones.power.isEmpty && (
            <PowerZone
              zone={zones.power}
              onAction={handleActionWithPowerManagement}
              className="zone-power"
              isDisabled={isControlDisabled}
            />
          )}

          {/* Media Stack Zone (②) - Show/Hide */}
          {zones['media-stack'] && !zones['media-stack'].isEmpty && (
            <MediaStackZone
              zone={zones['media-stack']}
              deviceStructure={deviceStructure}
              onAction={handleActionWithPowerManagement}
              className="zone-media-stack"
              isDisabled={isControlDisabled}
            />
          )}

          {/* Central Control Area - Always Present */}
          <div className="central-control">
              {/* Screen Zone (③) - Always Present (Left) */}
            <ScreenZone
              zone={zones.screen}
              onAction={handleActionWithPowerManagement}
              className="zone-screen"
            />

            {/* Menu Navigation Zone (⑦) - Always Present (Center) */}
            <MenuZone
              zone={zones.menu}
              onAction={handleActionWithPowerManagement}
              className="zone-menu"
            />

            {/* Volume Zone (④) - Always Present (Right) */}
            <VolumeZone
              zone={zones.volume}
              onAction={handleActionWithPowerManagement}
              className="zone-volume"
            />
          </div>

          {/* Apps Zone (⑤) - Always Present */}
          <AppsZone
            zone={zones.apps}
            deviceStructure={deviceStructure}
            className="zone-apps"
          />

          {/* Pointer Zone (⑥) - Always Present */}
          <PointerZone
            zone={zones.pointer}
            onAction={handleActionWithPowerManagement}
            className="zone-pointer"
          />
        </div>
      </div>

      {/* CSS Styles */}
      <style dangerouslySetInnerHTML={{
        __html: `
          .remote-control-container {
            /* Authentic Remote Control Appearance */
            width: 320px;
            max-width: 90vw;
            min-height: 850px;
            aspect-ratio: 4/10.5;
            
            /* Dark Grey Metal Gradient */
            background: linear-gradient(135deg, 
              #2a2a2a 0%, 
              #1a1a1a 25%, 
              #2a2a2a 50%, 
              #1a1a1a 75%, 
              #2a2a2a 100%
            );
            
            /* Physical Remote Appearance */
            border-radius: 24px;
            border: 2px solid #404040;
            box-shadow: 
              0 8px 32px rgba(0, 0, 0, 0.3),
              inset 0 1px 0 rgba(255, 255, 255, 0.1),
              inset 0 -1px 0 rgba(0, 0, 0, 0.3);
            
            /* Layout */
            display: flex;
            flex-direction: column;
            padding: 16px;
            gap: 12px;
            /* FIX: Ensure all content stays within container */
            overflow: hidden;
            position: relative;
          }

          .remote-header {
            /* Header Styling */
            padding: 8px 16px;
            border-radius: 12px;
            background: rgba(0, 0, 0, 0.3);
            border: 1px solid rgba(255, 255, 255, 0.1);
          }

          .remote-zones {
            /* Zones Container */
            display: flex;
            flex-direction: column;
            gap: 8px;
            flex: 1;
          }

          .central-control {
            /* Central Control Area - Always Present */
            display: grid;
            grid-template-columns: 1fr 2fr 1fr;
            gap: 8px;
            padding: 8px 0px;
            background: rgba(0, 0, 0, 0.2);
            border-radius: 16px;
            border: 1px solid rgba(255, 255, 255, 0.05);
            min-height: 200px;
            /* FIX: Maintain grid layout integrity */
            position: relative;
            width: 100%;
            max-width: 100%;
            /* Ensure proper grid behavior */
            grid-template-rows: 1fr;
            align-items: stretch;
          }

          /* Zone Base Styling */
          .zone-power {
            /* Show/Hide Zones */
            padding: 12px;
            border-radius: 12px;
            background: rgba(255, 255, 255, 0.05);
            border: 1px solid rgba(255, 255, 255, 0.1);
          }

          .zone-apps {
            /* Show/Hide Zones with Legend Support */
            position: relative;
            border-radius: 12px;
            background: rgba(255, 255, 255, 0.05);
            border: 1px solid rgba(255, 255, 255, 0.1);
            padding-top: 12px;
          }

          .zone-pointer {
            /* Pointer Zone - Flex to fill remaining space */
            position: relative;
            border-radius: 12px;
            background: rgba(255, 255, 255, 0.05);
            border: 1px solid rgba(255, 255, 255, 0.1);
            padding-top: 12px;
            flex: 1;
            display: flex;
            flex-direction: column;
          }

          .zone-media-stack {
            /* Media Stack - No border, just container styling */
            padding: 12px;
            border-radius: 12px;
            background: rgba(255, 255, 255, 0.05);
          }

          /* Individual Media Stack Groups */
          .media-stack-group {
            /* Individual control groups within media stack */
            position: relative;
            border-radius: 8px;
            background: rgba(255, 255, 255, 0.03);
            border: 1px solid rgba(255, 255, 255, 0.1);
            margin-bottom: 4px;
            padding-top: 12px;
          }

          .media-stack-group:last-child {
            margin-bottom: 0;
          }

          .media-stack-legend {
            /* Label that breaks through the border */
            position: absolute;
            top: -6px;
            left: 12px;
            padding: 0 6px;
            background: linear-gradient(135deg, 
              #2a2a2a 0%, 
              #1a1a1a 25%, 
              #2a2a2a 50%, 
              #1a1a1a 75%, 
              #2a2a2a 100%
            );
            font-size: 10px;
            font-weight: 600;
            color: rgba(255, 255, 255, 0.7);
            text-transform: uppercase;
            letter-spacing: 0.5px;
            z-index: 1;
          }

          .media-stack-content {
            /* Content area inside the bordered group */
            padding: 8px;
          }

          /* Generic Zone Legend Styling */
          .zone-legend {
            /* Label that breaks through the border for zone containers */
            position: absolute;
            top: -6px;
            left: 12px;
            padding: 0 6px;
            background: linear-gradient(135deg, 
              #2a2a2a 0%, 
              #1a1a1a 25%, 
              #2a2a2a 50%, 
              #1a1a1a 75%, 
              #2a2a2a 100%
            );
            font-size: 10px;
            font-weight: 600;
            color: rgba(255, 255, 255, 0.7);
            text-transform: uppercase;
            letter-spacing: 0.5px;
            z-index: 1;
          }

          .zone-content {
            /* Content area inside the bordered zone */
            padding: 8px;
          }

          .pointer-content {
            /* Pointer zone content should fill available space dynamically */
            flex: 1;
            min-height: 120px;
            padding: 4px;
          }

          .pointer-content * {
            /* Remove any selection indicators or focus outlines */
            outline: none !important;
            user-select: none;
          }

          .zone-screen,
          .zone-menu,
          .zone-volume {
            /* Always Present Zones */
            padding: 8px;
            border-radius: 8px;
            background: rgba(255, 255, 255, 0.03);
            border: 1px solid rgba(255, 255, 255, 0.08);
            min-height: 150px;
            display: flex;
            flex-direction: column;
            justify-content: center;
            /* FIX: Maintain grid item constraints */
            width: 100%;
            min-width: 0;
            box-sizing: border-box;
          }

          /* Zone-Specific Styling */
          .zone-power {
            /* Power Zone - 3 button layout */
            display: grid;
            grid-template-columns: 1fr 1fr 1fr;
            gap: 8px;
          }

          .zone-media-stack {
            /* Media Stack - Vertical sections */
            display: flex;
            flex-direction: column;
            gap: 8px;
          }

          .zone-screen {
            /* Screen Zone - Vertical button alignment */
            align-items: flex-start;
            /* FIX: Align left edge with inputs zone (left-to-left) */
            grid-column: 1;
            justify-self: stretch;
            margin-left: -8px;
          }

          .zone-menu {
            /* Menu Zone - NavCluster center */
            align-items: center;
            /* FIX: Ensure proper grid positioning */
            grid-column: 2;
            justify-self: stretch;
          }

          .zone-volume {
            /* Volume Zone - Vertical controls */
            align-items: flex-end;
            /* FIX: Push volume zone to align with right edge of inputs zone */
            grid-column: 3;
            justify-self: stretch;
            margin-right: -8px;
          }

          .zone-apps {
            /* Apps Zone - Dropdown */
            display: flex;
            flex-direction: column;
            gap: 4px;
          }

          .zone-pointer {
            /* Pointer Zone - Trackpad area */
            min-height: 120px;
            background: rgba(255, 255, 255, 0.08);
          }

          /* Empty Zone Styling */
          .zone-empty {
            /* Empty Always-Present Zones */
            border: 2px dashed rgba(255, 255, 255, 0.2);
            background: rgba(255, 255, 255, 0.02);
            display: flex;
            align-items: center;
            justify-content: center;
            color: rgba(255, 255, 255, 0.4);
            font-size: 12px;
            text-align: center;
          }

          /* Responsive Behavior */
          @media (max-width: 640px) {
            .remote-control-container {
              width: 280px;
              min-height: 730px;
              padding: 12px;
              gap: 8px;
            }
            
            .central-control {
              min-height: 160px;
              gap: 6px;
              padding: 6px;
            }
            
            .zone-screen,
            .zone-menu,
            .zone-volume {
              min-height: 120px;
              padding: 6px;
            }
          }

          /* iPad Portrait Optimization */
          @media (min-width: 768px) and (max-width: 1024px) and (orientation: portrait) {
            .remote-control-container {
              width: 360px;
              min-height: 950px;
            }
            
            .central-control {
              min-height: 240px;
            }
            
            .zone-screen,
            .zone-menu,
            .zone-volume {
              min-height: 180px;
            }
          }
        `
      }} />
    </div>
  );
}