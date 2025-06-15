import type { DeviceStructure, UISection, ProcessedAction } from '../../types/ProcessedDevice';
import { PointerPadGenerator } from './PointerPadGenerator';
import { SliderControlGenerator } from './SliderControlGenerator';

export class DevicePageTemplate {
  private pointerPadGenerator = new PointerPadGenerator();
  private sliderControlGenerator = new SliderControlGenerator();
  
  generateComponent(structure: DeviceStructure): string {
    return `
// Auto-generated from device config - DO NOT EDIT
import React, { useState } from 'react';
import { useLogStore } from '../../stores/useLogStore';
import { useExecuteDeviceAction } from '../../hooks/useApi';
import { useSettingsStore } from '../../stores/useSettingsStore';
import { Button } from '../../components/ui/button';
import NavCluster from '../../components/NavCluster';
import PointerPad from '../../components/PointerPad';
import SliderControl from '../../components/SliderControl';
import { Icon } from '../../components/icons';

function ${this.formatComponentName(structure.deviceId)}Page() {
  const { addLog } = useLogStore();
  const executeAction = useExecuteDeviceAction();
  const { statePanelOpen } = useSettingsStore();

${this.generateStateVariables(structure.uiSections)}

  const handleAction = (action: string, payload?: any) => {
    executeAction.mutate({ 
      deviceId: '${structure.deviceId}', 
      action: { action: action, params: payload } 
    });
    addLog({
      level: 'info',
      message: \`Action: \${action}\`,
      details: payload
    });
  };

  return (
    <div className={\`\${statePanelOpen ? 'p-4 space-y-4' : 'p-6 space-y-6'}\`}>
      <div className="text-center">
        <h1 className={\`\${statePanelOpen ? 'text-xl' : 'text-2xl'} font-bold\`}>${structure.deviceName}</h1>
        <p className={\`text-gray-600 \${statePanelOpen ? 'text-sm' : ''}\`}>Device Class: ${structure.deviceClass}</p>
      </div>

      <div className={\`grid grid-cols-1 lg:grid-cols-2 \${statePanelOpen ? 'gap-3' : 'gap-6'}\`}>
        ${this.generateSections(structure.uiSections)}
      </div>
    </div>
  );
}

export default ${this.formatComponentName(structure.deviceId)}Page;
    `.trim();
  }
  
  private generateSections(sections: UISection[]): string {
    return sections.map(section => `
        <div className={\`\${statePanelOpen ? 'space-y-2' : 'space-y-4'}\`}>
          <h2 className={\`\${statePanelOpen ? 'text-base' : 'text-lg'} font-semibold\`}>${section.sectionName}</h2>
          ${this.generateSectionContent(section)}
        </div>
    `).join('\n');
  }
  
  private generateSectionContent(section: UISection): string {
    switch (section.componentType) {
      case 'ButtonGrid':
        return this.generateButtonGrid(section.actions);
      case 'NavCluster':
        return this.generateNavCluster(section.actions);
      case 'PointerPad':
        return this.pointerPadGenerator.generate(section.actions);
      case 'SliderControl':
        return this.sliderControlGenerator.generate(section.actions);
      default:
        return `<div>Component type ${section.componentType} not implemented yet</div>`;
    }
  }
  
  private generateButtonGrid(actions: ProcessedAction[]): string {
    return `
          <div className={\`grid grid-cols-2 \${statePanelOpen ? 'gap-1' : 'gap-2'}\`}>
            ${actions.map(action => this.generateButton(action)).join('\n            ')}
          </div>
    `;
  }
  
  private generateNavCluster(actions: ProcessedAction[]): string {
    // For NavCluster, we need to identify directional actions
    const upAction = actions.find(a => a.actionName.toLowerCase().includes('up'));
    const downAction = actions.find(a => a.actionName.toLowerCase().includes('down'));
    const leftAction = actions.find(a => a.actionName.toLowerCase().includes('left'));
    const rightAction = actions.find(a => a.actionName.toLowerCase().includes('right'));
    const okAction = actions.find(a => a.actionName.toLowerCase().includes('ok') || a.actionName.toLowerCase().includes('enter'));
    
    // If we have directional actions, use NavCluster component
    if (upAction || downAction || leftAction || rightAction || okAction) {
      return `
          <NavCluster
            onUp={${upAction ? `() => handleAction('${upAction.actionName}')` : 'undefined'}}
            onDown={${downAction ? `() => handleAction('${downAction.actionName}')` : 'undefined'}}
            onLeft={${leftAction ? `() => handleAction('${leftAction.actionName}')` : 'undefined'}}
            onRight={${rightAction ? `() => handleAction('${rightAction.actionName}')` : 'undefined'}}
            onOk={${okAction ? `() => handleAction('${okAction.actionName}')` : 'undefined'}}
            className={\`w-full mx-auto \${statePanelOpen ? 'max-w-xs' : 'max-w-sm'}\`}
          />
      `;
    }
    
    // Fallback to button grid if no directional actions found
    return this.generateButtonGrid(actions);
  }
  
  private generateButton(action: ProcessedAction): string {
    return `
      <Button
        variant="secondary"
        size={\`\${statePanelOpen ? 'sm' : 'default'}\`}
        onClick={() => handleAction('${action.actionName}')}
        className={\`flex items-center \${statePanelOpen ? 'gap-1 text-xs' : 'gap-2'}\`}
        title="${action.description}"
      >
        <Icon
          library="${action.icon.iconLibrary}"
          name="${action.icon.iconName}"
          size={\`\${statePanelOpen ? 'sm' : 'md'}\`}
          fallback="${action.icon.fallbackIcon}"
        />
        ${action.displayName}
      </Button>`;
  }
  
  // Icon imports are now handled by the unified Icon component
  // No need for individual icon imports anymore
  
  private formatComponentName(deviceId: string): string {
    return deviceId
      .split(/[-_]/)
      .map(part => part.charAt(0).toUpperCase() + part.slice(1).toLowerCase())
      .join('');
  }
  
  private generateStateVariables(sections: UISection[]): string {
    const stateVars: string[] = [];
    
    sections.forEach(section => {
      if (section.componentType === 'SliderControl') {
        const sliderVars = this.sliderControlGenerator.generateStateVariables(section.actions);
        if (sliderVars) {
          stateVars.push(sliderVars);
        }
      }
    });
    
    return stateVars.length > 0 ? stateVars.join('\n') : '';
  }
} 