// Zone Detection Utility - Phase 1
// Maps device groups and actions to remote control zones

import type { DeviceGroups, DeviceGroup } from '../types/DeviceConfig';
import type { ProcessedAction } from '../types/ProcessedDevice';
import type { 
  RemoteZone, 
  ZoneDetectionConfig 
} from '../types/RemoteControlLayout';

// Import the default configuration as a regular import
const DEFAULT_ZONE_DETECTION: ZoneDetectionConfig = {
  powerGroupNames: ['power', 'power_control', 'main_power'],
  powerActionNames: ['power', 'power_on', 'power_off', 'power_toggle', 'zone2_power'],
  
  inputsGroupNames: ['inputs', 'input_selection', 'sources', 'input_control'],
  playbackGroupNames: ['playback', 'media_control', 'transport', 'player'],
  tracksGroupNames: ['tracks', 'track_control', 'navigation', 'track_nav'],
  tracksActionNames: ['audio', 'subtitles', 'language', 'track', 'subtitle', 'tray', 'eject'],
  
  volumeGroupNames: ['volume', 'volume_control', 'audio', 'sound'],
  volumeActionNames: ['volume', 'volume_up', 'volume_down', 'mute', 'set_volume'],
  
  menuGroupNames: ['menu', 'navigation', 'nav', 'menu_nav', 'ui_nav'],
  navigationActionNames: ['up', 'down', 'left', 'right', 'ok', 'enter', 'select', 'back', 'menu', 'home', 'settings'],
  
  screenGroupNames: ['screen', 'display', 'video', 'picture'],
  screenActionNames: ['aspect', 'zoom', 'display_mode', 'picture_mode', 'screen', 'ratio', 'letterbox'],
  
  appsGroupNames: ['apps', 'applications', 'channels', 'streaming'],
  appsActionNames: ['launch_app', 'select_app', 'app', 'channel'],
  
  pointerGroupNames: ['pointer', 'cursor', 'mouse', 'trackpad'],
  pointerActionNames: ['move', 'click', 'drag', 'scroll', 'cursor', 'pointer_gesture', 'touch_at_position', 'gesture', 'touch']
};

export class ZoneDetection {
  private config: ZoneDetectionConfig;

  constructor(config: ZoneDetectionConfig = DEFAULT_ZONE_DETECTION) {
    this.config = config;
  }

  /**
   * Analyze device groups and generate remote control zones
   */
  public analyzeDeviceGroups(groups: DeviceGroups, actions: ProcessedAction[]): RemoteZone[] {
    const zones: RemoteZone[] = [];

    // Create all 7 zones
    zones.push(this.createPowerZone(groups, actions));
    zones.push(this.createMediaStackZone(groups, actions));
    zones.push(this.createScreenZone(groups, actions));
    zones.push(this.createVolumeZone(groups, actions));
    zones.push(this.createAppsZone(groups, actions));
    zones.push(this.createMenuZone(groups, actions));
    zones.push(this.createPointerZone(groups, actions));

    return zones;
  }

  /**
   * Power Zone (①) - Show/Hide Zone
   */
  private createPowerZone(groups: DeviceGroups, actions: ProcessedAction[]): RemoteZone {
    const powerGroups = this.findGroupsByName(groups, this.config.powerGroupNames);
    const powerActions = this.findActionsByName(actions, this.config.powerActionNames);
    
    const isEmpty = powerGroups.length === 0 && powerActions.length === 0;

    return {
      zoneId: 'power',
      zoneName: 'Power Control',
      zoneType: 'power',
      showHide: true, // Show/Hide zone
      isEmpty,
      content: {
        powerButtons: this.createPowerButtonsConfig(powerActions)
      },
      layout: {
        columns: 3,
        spacing: 'normal',
        alignment: 'center'
      }
    };
  }

  /**
   * Media Stack Zone (②) - Show/Hide Zone
   */
  private createMediaStackZone(groups: DeviceGroups, actions: ProcessedAction[]): RemoteZone {
    const inputsGroups = this.findGroupsByName(groups, this.config.inputsGroupNames);
    const playbackGroups = this.findGroupsByName(groups, this.config.playbackGroupNames);
    const tracksGroups = this.findGroupsByName(groups, this.config.tracksGroupNames);
    const tracksActions = this.findActionsByName(actions, this.config.tracksActionNames);
    
    const isEmpty = inputsGroups.length === 0 && playbackGroups.length === 0 && tracksGroups.length === 0 && tracksActions.length === 0;

    console.log(`🔍 [ZoneDetection] Media Stack analysis:`, {
      inputsGroups: inputsGroups.length,
      playbackGroups: playbackGroups.length,
      tracksGroups: tracksGroups.length,
      tracksActions: tracksActions.length,
      isEmpty,
      willCreateInputsDropdown: inputsGroups.length > 0
    });

    return {
      zoneId: 'media-stack',
      zoneName: 'Media Stack',
      zoneType: 'media-stack',
      showHide: true, // Show/Hide zone
      isEmpty,
      content: {
        inputsDropdown: inputsGroups.length > 0 ? {
          type: 'inputs',
          populationMethod: 'api', // AuralicDevice uses API
          apiAction: 'get_available_inputs',
          setAction: 'set_input',
          options: [],
          loading: false,
          empty: true
        } : undefined,
        playbackSection: playbackGroups.length > 0 ? {
          actions: this.getActionsFromGroups(playbackGroups, actions),
          layout: 'horizontal'
        } : undefined,
        tracksSection: (tracksGroups.length > 0 || tracksActions.length > 0) ? {
          actions: tracksGroups.length > 0 
            ? this.getActionsFromGroups(tracksGroups, actions)
            : tracksActions,
          layout: 'horizontal'
        } : undefined
      },
      layout: {
        spacing: 'normal',
        orientation: 'vertical'
      }
    };
  }

  /**
   * Screen Zone (③) - Always Present Zone
   */
  private createScreenZone(groups: DeviceGroups, actions: ProcessedAction[]): RemoteZone {
    const screenGroups = this.findGroupsByName(groups, this.config.screenGroupNames);
    const screenActions = this.findActionsByName(actions, this.config.screenActionNames);
    
    const isEmpty = screenGroups.length === 0 && screenActions.length === 0;

    return {
      zoneId: 'screen',
      zoneName: 'Screen Controls',
      zoneType: 'screen',
      showHide: false, // Always present
      isEmpty,
      content: {
        screenActions: screenActions
      },
      layout: {
        orientation: 'vertical',
        alignment: 'left',
        spacing: 'compact'
      }
    };
  }

  /**
   * Volume Zone (④) - Always Present Zone
   */
  private createVolumeZone(groups: DeviceGroups, actions: ProcessedAction[]): RemoteZone {
    const volumeGroups = this.findGroupsByName(groups, this.config.volumeGroupNames);
    const volumeActions = this.findActionsByName(actions, this.config.volumeActionNames);
    
    const isEmpty = volumeGroups.length === 0 && volumeActions.length === 0;

    // Priority-based population logic
    const hasSliderAction = volumeActions.find(a => 
      a.parameters.some(p => p.type === 'range')
    );

    return {
      zoneId: 'volume',
      zoneName: 'Volume Control',
      zoneType: 'volume',
      showHide: false, // Always present
      isEmpty,
      content: hasSliderAction ? {
        volumeSlider: {
          action: hasSliderAction,
          muteAction: volumeActions.find(a => a.actionName.toLowerCase().includes('mute')),
          orientation: 'vertical',
          showValue: true
        }
      } : {
        volumeButtons: [{
          upAction: volumeActions.find(a => a.actionName.toLowerCase().includes('up')),
          downAction: volumeActions.find(a => a.actionName.toLowerCase().includes('down')),
          muteAction: volumeActions.find(a => a.actionName.toLowerCase().includes('mute'))
        }]
      },
      layout: {
        priority: hasSliderAction ? 1 : 2,
        orientation: 'vertical',
        alignment: 'right',
        spacing: 'compact'
      }
    };
  }

  /**
   * Apps Zone (⑤) - Show/Hide Zone
   */
  private createAppsZone(groups: DeviceGroups, actions: ProcessedAction[]): RemoteZone {
    const appsGroups = this.findGroupsByName(groups, this.config.appsGroupNames);
    const appsActions = this.findActionsByName(actions, this.config.appsActionNames);
    
    const isEmpty = appsGroups.length === 0 && appsActions.length === 0;

    return {
      zoneId: 'apps',
      zoneName: 'Applications',
      zoneType: 'apps',
      showHide: true, // Show/Hide zone
      isEmpty,
      content: {
        appsDropdown: !isEmpty ? {
          type: 'apps',
          populationMethod: 'api', // Apps typically use API
          apiAction: 'get_available_apps',
          setAction: 'launch_app',
          options: [],
          loading: false,
          empty: true
        } : undefined
      },
      layout: {
        spacing: 'normal'
      }
    };
  }

  /**
   * Menu Zone (⑥) - Always Present Zone (Center of central control)
   * NavCluster should ONLY be populated with actions from menu groups
   */
  private createMenuZone(groups: DeviceGroups, actions: ProcessedAction[]): RemoteZone {
    const menuGroups = this.findGroupsByName(groups, this.config.menuGroupNames);
    // ONLY get actions from menu groups, not from all device actions
    const menuActions = this.getActionsFromGroups(menuGroups, actions);
    
    const isEmpty = menuGroups.length === 0;

    // Helper to find navigation actions within menu group actions only
    const findMenuNavAction = (pattern: string) => {
      const menuAction = menuActions.find(a => {
        const actionName = a.actionName.toLowerCase();
        return actionName.includes(pattern) || actionName === pattern;
      });
      
      // If menu groups don't have the action, look in all actions BUT NEVER map volume actions to navigation
      if (!menuAction) {
        return actions.find(a => {
          const actionName = a.actionName.toLowerCase();
          const isVolumeAction = actionName.includes('volume');
          
          // NEVER map volume actions to navigation - they belong in volume zone
          if (isVolumeAction) {
            return false;
          }
          
          return actionName.includes(pattern) || actionName === pattern;
        });
      }
      
      return menuAction;
    };

    // Helper to find auxiliary actions across ALL device actions (not just menu groups)
    // Only match exact action names to avoid conflicts with navigation actions
    const findAuxAction = (pattern: string) => {
      return actions.find(a => {
        const actionName = a.actionName.toLowerCase();
        // Exact match only - avoid matching 'menu' to 'menu_up' or 'back' to 'rewind_backward'
        return actionName === pattern;
      });
    };

    return {
      zoneId: 'menu',
      zoneName: 'Navigation',
      zoneType: 'menu',
      showHide: false, // Always present
      isEmpty,
      content: {
        navigationCluster: {
          upAction: findMenuNavAction('up'),
          downAction: findMenuNavAction('down'),
          leftAction: findMenuNavAction('left'),
          rightAction: findMenuNavAction('right'),
          okAction: findMenuNavAction('ok') || findMenuNavAction('enter') || findMenuNavAction('select'),
          // AUX buttons populated from ANY device actions
          aux1Action: findAuxAction('home') || findAuxAction('menu_exit'),
          aux2Action: findAuxAction('menu'),
          aux3Action: findAuxAction('back'),
          aux4Action: findAuxAction('settings') || findAuxAction('exit')
        }
      },
      layout: {
        alignment: 'center',
        spacing: 'normal'
      }
    };
  }

  /**
   * Pointer Zone (⑦) - Show/Hide Zone
   */
  private createPointerZone(groups: DeviceGroups, actions: ProcessedAction[]): RemoteZone {
    const pointerGroups = this.findGroupsByName(groups, this.config.pointerGroupNames);
    const pointerActions = this.findActionsByName(actions, this.config.pointerActionNames);
    
    const isEmpty = pointerGroups.length === 0 && pointerActions.length === 0;

    // Find specific pointer actions
    const gestureAction = pointerActions.find(a => 
      a.actionName.toLowerCase().includes('gesture') || a.actionName.toLowerCase().includes('pointer_gesture')
    );
    const touchAction = pointerActions.find(a => 
      a.actionName.toLowerCase().includes('touch_at_position') || a.actionName.toLowerCase().includes('touch')
    );
    const moveAction = pointerActions.find(a => a.actionName.toLowerCase().includes('move'));
    const clickAction = pointerActions.find(a => a.actionName.toLowerCase().includes('click'));
    const dragAction = pointerActions.find(a => a.actionName.toLowerCase().includes('drag'));
    const scrollAction = pointerActions.find(a => a.actionName.toLowerCase().includes('scroll'));

    return {
      zoneId: 'pointer',
      zoneName: 'Pointer Control',
      zoneType: 'pointer',
      showHide: true, // Show/Hide zone
      isEmpty,
      content: {
        pointerPad: !isEmpty ? {
          moveAction: gestureAction || moveAction || pointerActions[0],
          clickAction: touchAction || clickAction,
          dragAction: dragAction,
          scrollAction: scrollAction
        } : undefined
      },
      layout: {
        spacing: 'normal'
      }
    };
  }

  // Utility methods
  private findGroupsByName(groups: DeviceGroups, targetNames: string[]): DeviceGroup[] {
    if (!groups.groups) return [];
    
    return groups.groups.filter(group =>
      targetNames.some(name => 
        group.group_name.toLowerCase().includes(name.toLowerCase())
      )
    );
  }

  private findActionsByName(actions: ProcessedAction[], targetNames: string[]): ProcessedAction[] {
    return actions.filter(action =>
      targetNames.some(name => 
        action.actionName.toLowerCase().includes(name.toLowerCase())
      )
    );
  }

  private getActionsFromGroups(groups: DeviceGroup[], allActions: ProcessedAction[]): ProcessedAction[] {
    const groupActionNames = groups.flatMap(group => 
      group.actions.map(action => action.name)
    );
    
    return allActions.filter(action =>
      groupActionNames.includes(action.actionName)
    );
  }

  private createPowerButtonsConfig(powerActions: ProcessedAction[]): any[] {
    // EMotiva special case handling will be added in Phase 4
    // For Phase 1, just basic power button layout
    
    const powerOffAction = powerActions.find(a => a.actionName.toLowerCase().includes('off'));
    const powerOnAction = powerActions.find(a => a.actionName.toLowerCase().includes('on'));
    const powerToggleAction = powerActions.find(a => 
      !a.actionName.toLowerCase().includes('off') && 
      !a.actionName.toLowerCase().includes('on') &&
      a.actionName.toLowerCase().includes('power')
    );

    const buttons: any[] = [];

    if (powerOffAction) {
      buttons.push({
        position: 'left',
        action: powerOffAction,
        buttonType: 'power-off'
      });
    }

    if (powerOnAction) {
      buttons.push({
        position: 'right',
        action: powerOnAction,
        buttonType: 'power-on'
      });
    } else if (powerToggleAction && !powerOffAction) {
      // Single toggle case
      buttons.push({
        position: 'left',
        action: powerToggleAction,
        buttonType: 'power-toggle'
      });
    }

    return buttons;
  }
} 