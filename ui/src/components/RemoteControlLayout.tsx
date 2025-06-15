
import React, { useState } from 'react';
import { cn } from '../lib/utils';
import { Button } from './ui/button';
import NavCluster from './NavCluster';
import PointerPad from './PointerPad';
import { Icon } from './icons';
import type { RemoteZone, RemoteDeviceStructure, PowerButtonConfig, VolumeButtonConfig } from '../types/RemoteControlLayout';
import { useInputsData, useAppsData, useInputSelection, useAppLaunching } from '../hooks/useRemoteControlData';

// Power Zone - 3-button layout with EMotiva special case
const PowerZone = ({ zone, onAction, className }: { zone?: RemoteZone; onAction: (action: string, payload?: any) => void; className?: string }) => {
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

  const getButtonVariant = (buttonType: string) => {
    switch (buttonType) {
      case 'power-off':
      case 'zone2-power':
        return 'destructive' as const;
      case 'power-on':
      case 'power-toggle':
        return 'default' as const;
      default:
        return 'secondary' as const;
    }
  };

  return (
    <div className={cn("zone-power", className)}>
      {/* Left Position */}
      {leftButton ? (
        <Button
          variant={getButtonVariant(leftButton.buttonType)}
          size="sm"
          onClick={() => handlePowerAction(leftButton)}
          className="h-12 text-xs"
        >
          <Icon
            library={leftButton.action.icon.iconLibrary as 'material'}
            name={leftButton.action.icon.iconName}
            fallback={leftButton.action.icon.fallbackIcon}
            size="sm"
            className="w-4 h-4 mr-1"
          />
          {leftButton.action.displayName}
        </Button>
      ) : (
        <div></div>
      )}

      {/* Middle Position */}
      {middleButton ? (
        <Button
          variant={getButtonVariant(middleButton.buttonType)}
          size="sm"
          onClick={() => handlePowerAction(middleButton)}
          className="h-12 text-xs"
        >
          <Icon
            library={middleButton.action.icon.iconLibrary as 'material'}
            name={middleButton.action.icon.iconName}
            fallback={middleButton.action.icon.fallbackIcon}
            size="sm"
            className="w-4 h-4 mr-1"
          />
          {middleButton.action.displayName}
        </Button>
      ) : (
        <div></div>
      )}

      {/* Right Position */}
      {rightButton ? (
        <Button
          variant={getButtonVariant(rightButton.buttonType)}
          size="sm"
          onClick={() => handlePowerAction(rightButton)}
          className="h-12 text-xs"
        >
          <Icon
            library={rightButton.action.icon.iconLibrary as 'material'}
            name={rightButton.action.icon.iconName}
            fallback={rightButton.action.icon.fallbackIcon}
            size="sm"
            className="w-4 h-4 mr-1"
          />
          {rightButton.action.displayName}
        </Button>
      ) : (
        <div></div>
      )}
    </div>
  );
};

// Media Stack Zone - INPUTS, PLAYBACK, TRACKS sections
const MediaStackZone = ({ zone, deviceStructure, onAction, className }: { 
  zone?: RemoteZone; 
  deviceStructure: RemoteDeviceStructure;
  onAction: (action: string, payload?: any) => void; 
  className?: string 
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

  const { playbackSection, tracksSection } = zone.content;

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
      {/* INPUTS Section - Use dynamic data */}
      {(dynamicInputs.length > 0 || inputsLoading) && (
        <div className="inputs-section">
          <label className="text-xs text-white/70 mb-1 block">
            INPUTS {inputsLoading && "(Loading...)"}
          </label>
          {inputsError ? (
            <div className="text-red-400 text-xs mb-1">
              Error loading inputs: {inputsError}
            </div>
          ) : null}
          <select
            value={selectedInput}
            onChange={(e) => handleInputSelect(e.target.value)}
            className="w-full px-2 py-1 text-xs bg-black/30 border border-white/20 rounded text-white"
            disabled={inputsLoading}
          >
            <option value="">
              {inputsLoading ? "Loading inputs..." : "Select Input..."}
            </option>
            {dynamicInputs.map((option) => (
              <option key={option.id} value={option.id}>
                {option.displayName}
              </option>
            ))}
          </select>
        </div>
      )}

      {/* PLAYBACK Section */}
      {playbackSection && playbackSection.actions.length > 0 && (
        <div className="playback-section">
          <label className="text-xs text-white/70 mb-1 block">PLAYBACK</label>
          <div className="flex gap-1 flex-wrap">
            {playbackSection.actions.map((action, index) => (
              <Button
                key={index}
                variant="secondary"
                size="sm"
                onClick={() => handlePlaybackAction(action)}
                className="h-8 px-2 text-xs flex-1 min-w-fit"
              >
                <Icon
                  library={action.icon.iconLibrary as 'material'}
                  name={action.icon.iconName}
                  fallback={action.icon.fallbackIcon}
                  size="sm"
                  className="w-3 h-3 mr-1"
                />
                {action.displayName}
              </Button>
            ))}
          </div>
        </div>
      )}

      {/* TRACKS Section */}
      {tracksSection && tracksSection.actions.length > 0 && (
        <div className="tracks-section">
          <label className="text-xs text-white/70 mb-1 block">TRACKS</label>
          <div className="flex gap-1">
            {tracksSection.actions.map((action, index) => (
              <Button
                key={index}
                variant="secondary"
                size="sm"
                onClick={() => handlePlaybackAction(action)}
                className="h-8 px-2 text-xs flex-1"
              >
                <Icon
                  library={action.icon.iconLibrary as 'material'}
                  name={action.icon.iconName}
                  fallback={action.icon.fallbackIcon}
                  size="sm"
                  className="w-3 h-3 mr-1"
                />
                {action.displayName}
              </Button>
            ))}
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
      <div className="flex flex-col gap-1">
        {screenActions.map((action, index) => (
          <Button
            key={index}
            variant="secondary"
            size="sm"
            onClick={() => handleScreenAction(action)}
            className="h-8 px-2 text-xs justify-start"
          >
            <Icon
              library={action.icon.iconLibrary as 'material'}
              name={action.icon.iconName}
              fallback={action.icon.fallbackIcon}
              size="sm"
              className="w-3 h-3 mr-1"
            />
            {action.displayName}
          </Button>
        ))}
      </div>
    </div>
  );
};

// Volume Zone - Priority-based (slider vs buttons) with vertical orientation
const VolumeZone = ({ zone, onAction, className }: { zone?: RemoteZone; onAction: (action: string, payload?: any) => void; className?: string }) => {
  const [volume, setVolume] = useState(50);

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

  // Priority 1: Slider + Mute
  if (volumeSlider) {
    return (
      <div className={cn("zone-volume", className)}>
        <div className="flex flex-col items-center gap-2 h-full">
          {/* Volume Value Display */}
          <div className="text-xs text-white/70">{volume}</div>
          
          {/* Vertical Slider */}
          <div className="flex-1 flex items-center">
            <input
              type="range"
              min="0"
              max="100"
              value={volume}
              onChange={(e) => handleVolumeSlider(Number(e.target.value))}
              className="vertical-slider"
                             style={{
                 WebkitAppearance: 'slider-vertical',
                 height: '100px',
                 width: '20px',
                 transform: 'rotate(-90deg)'
               }}
            />
          </div>

          {/* Mute Button */}
          {volumeSlider.muteAction && (
            <Button
              variant="secondary"
              size="sm"
              onClick={() => handleVolumeButton(volumeSlider.muteAction)}
              className="h-6 w-12 text-xs"
            >
              <Icon
                library={volumeSlider.muteAction.icon.iconLibrary as 'material'}
                name={volumeSlider.muteAction.icon.iconName}
                fallback={volumeSlider.muteAction.icon.fallbackIcon}
                size="sm"
                className="w-3 h-3"
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
              variant="secondary"
              size="sm"
              onClick={() => handleVolumeButton(buttons.upAction)}
              className="h-8 w-12 text-xs"
            >
              <Icon
                library={buttons.upAction.icon.iconLibrary as 'material'}
                name={buttons.upAction.icon.iconName}
                fallback={buttons.upAction.icon.fallbackIcon}
                size="sm"
                className="w-3 h-3"
              />
            </Button>
          )}

          {/* Volume Down */}
          {buttons.downAction && (
            <Button
              variant="secondary"
              size="sm"
              onClick={() => handleVolumeButton(buttons.downAction)}
              className="h-8 w-12 text-xs"
            >
              <Icon
                library={buttons.downAction.icon.iconLibrary as 'material'}
                name={buttons.downAction.icon.iconName}
                fallback={buttons.downAction.icon.fallbackIcon}
                size="sm"
                className="w-3 h-3"
              />
            </Button>
          )}

          {/* Mute */}
          {buttons.muteAction && (
            <Button
              variant="secondary"
              size="sm"
              onClick={() => handleVolumeButton(buttons.muteAction)}
              className="h-8 w-12 text-xs"
            >
              <Icon
                library={buttons.muteAction.icon.iconLibrary as 'material'}
                name={buttons.muteAction.icon.iconName}
                fallback={buttons.muteAction.icon.fallbackIcon}
                size="sm"
                className="w-3 h-3"
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

  // Hide zone completely if no apps available and not loading
  if ((!zone?.content?.appsDropdown || zone.isEmpty) && dynamicApps.length === 0 && !appsLoading) {
    return null; // Show/hide zone - completely hidden when empty
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
      <label className="text-xs text-white/70 mb-1 block">
        APPS {appsLoading && "(Loading...)"}
      </label>
      {appsError ? (
        <div className="text-red-400 text-xs mb-1">
          Error loading apps: {appsError}
        </div>
      ) : null}
      <select
        value={selectedApp}
        onChange={(e) => handleAppSelect(e.target.value)}
        className="w-full px-3 py-2 text-sm bg-black/30 border border-white/20 rounded text-white"
        disabled={appsLoading}
      >
        <option value="">
          {appsLoading ? "Loading apps..." : "Select App..."}
        </option>
        {dynamicApps.map((option) => (
          <option key={option.id} value={option.id}>
            {option.displayName}
          </option>
        ))}
      </select>
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
        className="scale-75 transform"
      />
    </div>
  );
};

// Pointer Zone - PointerPad with lighter theme styling
const PointerZone = ({ zone, onAction, className }: { zone?: RemoteZone; onAction: (action: string, payload?: any) => void; className?: string }) => {
  if (!zone?.content?.pointerPad || zone.isEmpty) {
    return null; // Show/hide zone - completely hidden when empty
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
      <PointerPad
        mode="relative"
        onMove={handleMove}
        className="bg-white/10 border border-white/20 rounded-lg"
      />
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
  const { deviceName, remoteZones } = deviceStructure;

  // Zone lookup for easier access
  const zones = remoteZones.reduce((acc, zone) => {
    acc[zone.zoneId] = zone;
    return acc;
  }, {} as Record<string, RemoteZone>);

  return (
    <div className={cn("flex justify-center w-full", className)}>
      {/* Remote Control Container */}
      <div className="remote-control-container">
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
              onAction={onAction}
              className="zone-power"
            />
          )}

          {/* Media Stack Zone (②) - Show/Hide */}
          {zones['media-stack'] && !zones['media-stack'].isEmpty && (
            <MediaStackZone
              zone={zones['media-stack']}
              deviceStructure={deviceStructure}
              onAction={onAction}
              className="zone-media-stack"
            />
          )}

          {/* Central Control Area - Always Present */}
          <div className="central-control">
            {/* Screen Zone (③) - Always Present (Left) */}
            <ScreenZone
              zone={zones.screen}
              onAction={onAction}
              className="zone-screen"
            />

            {/* Menu Navigation Zone (⑦) - Always Present (Center) */}
            <MenuZone
              zone={zones.menu}
              onAction={onAction}
              className="zone-menu"
            />

            {/* Volume Zone (④) - Always Present (Right) */}
            <VolumeZone
              zone={zones.volume}
              onAction={onAction}
              className="zone-volume"
            />
          </div>

          {/* Apps Zone (⑤) - Show/Hide */}
          {zones.apps && !zones.apps.isEmpty && (
            <AppsZone
              zone={zones.apps}
              deviceStructure={deviceStructure}
              className="zone-apps"
            />
          )}

          {/* Pointer Zone (⑥) - Show/Hide */}
          {zones.pointer && !zones.pointer.isEmpty && (
            <PointerZone
              zone={zones.pointer}
              onAction={onAction}
              className="zone-pointer"
            />
          )}
        </div>
      </div>

      {/* CSS Styles */}
      <style dangerouslySetInnerHTML={{
        __html: `
          .remote-control-container {
            /* Authentic Remote Control Appearance */
            width: 320px;
            max-width: 90vw;
            min-height: 720px;
            aspect-ratio: 4/9;
            
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
            padding: 8px;
            background: rgba(0, 0, 0, 0.2);
            border-radius: 16px;
            border: 1px solid rgba(255, 255, 255, 0.05);
            min-height: 200px;
          }

          /* Zone Base Styling */
          .zone-power,
          .zone-media-stack,
          .zone-apps,
          .zone-pointer {
            /* Show/Hide Zones */
            padding: 12px;
            border-radius: 12px;
            background: rgba(255, 255, 255, 0.05);
            border: 1px solid rgba(255, 255, 255, 0.1);
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
          }

          .zone-menu {
            /* Menu Zone - NavCluster center */
            align-items: center;
          }

          .zone-volume {
            /* Volume Zone - Vertical controls */
            align-items: flex-end;
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
              min-height: 630px;
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
              min-height: 810px;
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