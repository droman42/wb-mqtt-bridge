import type { RemoteDeviceStructure } from '../types/RemoteControlLayout';

export interface GeneratedFile {
  filepath: string;
  content: string;
  checksum: string;
}

export interface DocumentationConfig {
  includeUsageExamples: boolean;
  includeStateDocumentation: boolean;
  includeActionDocumentation: boolean;
  includeIntegrationGuide: boolean;
  outputFormat: 'markdown' | 'html' | 'json';
}

export interface DeviceDocumentationSummary {
  totalDevices: number;
  deviceClasses: string[];
  totalActions: number;
  totalSections: number;
  generationDate: Date;
}

export class DocumentationGenerator {
  constructor() {}

  async generateDeviceDocumentation(structure: RemoteDeviceStructure): Promise<GeneratedFile> {
    const content = this.generateDeviceMarkdown(structure);
    const filepath = `docs/devices/${structure.deviceId}.md`;
    const checksum = this.generateChecksum(content);

    return {
      filepath,
      content,
      checksum
    };
  }

  async generateSystemDocumentation(devices: RemoteDeviceStructure[]): Promise<GeneratedFile> {
    const content = this.generateSystemMarkdown(devices);
    const filepath = 'docs/system-overview.md';
    const checksum = this.generateChecksum(content);

    return {
      filepath,
      content,
      checksum
    };
  }

  async generateAPIDocumentation(): Promise<GeneratedFile> {
    const content = this.generateAPIMarkdown();
    const filepath = 'docs/api-reference.md';
    const checksum = this.generateChecksum(content);

    return {
      filepath,
      content,
      checksum
    };
  }

  async generateUsageGuide(devices: RemoteDeviceStructure[]): Promise<GeneratedFile> {
    const content = this.generateUsageMarkdown(devices);
    const filepath = 'docs/usage-guide.md';
    const checksum = this.generateChecksum(content);

    return {
      filepath,
      content,
      checksum
    };
  }

  async generateDeviceClassDocumentation(deviceClass: string, devices: RemoteDeviceStructure[]): Promise<GeneratedFile> {
    const content = this.generateDeviceClassMarkdown(deviceClass, devices);
    const filepath = `docs/device-classes/${deviceClass.toLowerCase()}.md`;
    const checksum = this.generateChecksum(content);

    return {
      filepath,
      content,
      checksum
    };
  }

  private generateDeviceMarkdown(structure: RemoteDeviceStructure): string {
    const { deviceId, deviceName, deviceClass } = structure;

    return `# ${deviceName} - Generated Device Page

## Overview
- **Device ID**: \`${deviceId}\`
- **Device Class**: \`${deviceClass}\`
- **Layout Type**: Remote Control Layout
- **Generated At**: ${new Date().toISOString()}
- **Component File**: \`src/pages/devices/${deviceId}.gen.tsx\`

## Device Description
This page was automatically generated for the ${deviceName} device. It provides a user interface for controlling and monitoring the device through its available actions and state.

${this.generateRemoteZonesDocumentation(structure.remoteZones)}

## Integration

### React Router Integration
\`\`\`typescript
import ${this.formatComponentName(deviceId)}Page from './devices/${deviceId}.gen';

// Add to your router configuration
const deviceRoutes = [
  { 
    path: '/devices/${deviceId}', 
    component: ${this.formatComponentName(deviceId)}Page,
    name: '${deviceName}'
  }
];
\`\`\`

### Direct Component Usage
\`\`\`typescript
import React from 'react';
import ${this.formatComponentName(deviceId)}Page from './devices/${deviceId}.gen';

function App() {
  return (
    <div>
      <${this.formatComponentName(deviceId)}Page />
    </div>
  );
}
\`\`\`

## Customization

This generated file can be manually customized after generation. The system will warn before overwriting customized files.

### Common Customizations
- Modify button layouts and styling
- Add custom state management
- Integrate with additional APIs
- Add device-specific validations

### State Management
The component uses the following hooks for state management:
- \`useLogStore\` - For logging user actions
- \`useExecuteDeviceAction\` - For executing device commands

## Technical Details

### Dependencies
- React (functional component with hooks)
- \`useLogStore\` from \`../../stores/useLogStore\`
- \`useExecuteDeviceAction\` from \`../../hooks/useApi\`
- \`Button\` component from \`../../components/ui/button\`
- Icons from \`@mui/icons-material\` with custom SVG fallbacks

### Component Structure
- Main container with remote control proportions
- Device title section
- Remote control zones with authentic styling
- Consistent styling with Tailwind CSS

Last updated: ${new Date().toISOString()}
`;
  }

  private generateRemoteZonesDocumentation(remoteZones: any[]): string {
    return `## Remote Control Zones

${remoteZones.map(zone => this.generateZoneDocumentation(zone)).join('\n\n')}`;
  }

  private generateZoneDocumentation(zone: any): string {
    const behaviorType = zone.showHide ? 'Show/Hide Zone' : 'Always Present Zone';
    const emptyStatus = zone.isEmpty ? 'Empty' : 'Populated';
    
    return `### ${zone.zoneName} (${behaviorType})
- **Zone ID**: \`${zone.zoneId}\`
- **Zone Type**: \`${zone.zoneType}\`
- **Status**: ${emptyStatus}
- **Behavior**: ${zone.showHide ? 'Appears/disappears based on device capabilities' : 'Always visible, maintains layout space'}

${this.generateZoneContentDocumentation(zone.content, zone.zoneType)}`;
  }

  private generateZoneContentDocumentation(content: any, zoneType: string): string {
    const descriptions: Record<string, string> = {
      'power': 'Power control buttons with left/middle/right positioning',
      'media-stack': 'Input selection, playback controls, and track navigation',
      'screen': 'Vertical alignment area for screen control buttons',
      'volume': 'Priority-based volume control (slider or buttons)',
      'apps': 'Application selector dropdown',
      'menu': 'Central navigation cluster with directional controls',
      'pointer': 'Pointer pad / trackpad area for cursor control'
    };

    let contentDetails = descriptions[zoneType] || 'Zone-specific controls';
    
    // Add specific content details if available
    if (content) {
      const contentTypes = Object.keys(content).filter(key => content[key]);
      if (contentTypes.length > 0) {
        contentDetails += `\n- **Content Types**: ${contentTypes.join(', ')}`;
      }
    }

    return contentDetails;
  }

  private generateSystemMarkdown(devices: RemoteDeviceStructure[]): string {
    const summary = this.generateDocumentationSummary(devices);
    const devicesByClass = this.groupDevicesByClass(devices);

    return `# Generated Device System Documentation

## System Overview

This documentation covers the automatically generated device page system for smart home devices.

### Summary Statistics
- **Total Devices**: ${summary.totalDevices}
- **Device Classes**: ${summary.deviceClasses.length}
- **Total Remote Zones**: ${summary.totalSections}
- **Last Updated**: ${summary.generationDate.toISOString()}

## Supported Device Classes

${Object.entries(devicesByClass).map(([deviceClass, classDevices]) => 
`### ${this.formatClassDisplayName(deviceClass)}
- **Device Count**: ${classDevices.length}
- **Devices**: ${classDevices.map(d => `\`${d.deviceId}\``).join(', ')}
`).join('\n')}

## Architecture

### Code Generation Flow
1. **Configuration Fetch**: Device configuration retrieved from API
2. **Structure Analysis**: Device commands analyzed and grouped
3. **Zone Detection**: Remote control zones identified and populated
4. **Component Generation**: React component code generated
5. **File Output**: TypeScript files written to \`src/pages/devices/\`

### File Organization
\`\`\`
src/pages/devices/
├── index.gen.ts           # Router manifest
├── {device_id}.gen.tsx    # Generated device pages
└── {device_id}.hooks.ts   # Generated state hooks
\`\`\`

## Generated Components

${devices.map(device => {
  const zonesCount = device.remoteZones.length;
  const actionsCount = this.countRemoteZoneActions(device.remoteZones);
  
  return `### ${device.deviceName}
- **ID**: \`${device.deviceId}\`
- **Class**: \`${device.deviceClass}\`
- **File**: \`${device.deviceId}.gen.tsx\`
- **Route**: \`/devices/${device.deviceId}\`
- **Layout**: Remote Control
- **Zones**: ${zonesCount}
- **Actions**: ${actionsCount}`;
}).join('\n')}

Last updated: ${new Date().toISOString()}
`;
  }

  private generateAPIMarkdown(): string {
    return `# Device API Reference

## Overview
This document provides API reference for all generated device components using the remote control layout system.

## Remote Control System
All devices now use the unified remote control layout with 7 standard zones:
1. **Power Zone** - Device power controls
2. **Media Stack Zone** - Input selection, playback, and track controls
3. **Screen Zone** - Display and video controls
4. **Volume Zone** - Audio level controls
5. **Apps Zone** - Application launcher
6. **Menu Zone** - Navigation controls
7. **Pointer Zone** - Cursor/trackpad controls

## Device Actions
All device actions are executed through the unified action system:

\`\`\`typescript
const executeAction = useExecuteDeviceAction();

executeAction.mutate({
  deviceId: 'your_device_id',
  action: {
    name: 'action_name',
    params: { /* action parameters */ }
  }
});
\`\`\`

## Component Hooks

### useExecuteDeviceAction
Main hook for executing device actions.

### useLogStore
Hook for logging user interactions.

### useRemoteControlData
Hooks for dynamic dropdown data (inputs/apps).

Last updated: ${new Date().toISOString()}
`;
  }

  private generateUsageMarkdown(devices: RemoteDeviceStructure[]): string {
    return `# Device Usage Guide

## Getting Started

This guide explains how to use the generated device pages with the remote control layout system.

## Device Overview

You have ${devices.length} devices configured across ${this.getUniqueDeviceClasses(devices).length} device classes:

${this.getUniqueDeviceClasses(devices).map(deviceClass => `### ${this.formatClassDisplayName(deviceClass)}
${devices.filter(d => d.deviceClass === deviceClass).map(device => `- **${device.deviceName}** (\`${device.deviceId}\`) - [Access Page](/devices/${device.deviceId})`).join('\n')}
`).join('\n')}

## Remote Control Interface

All devices use a consistent remote control interface with these zones:

### Power Zone
- Power ON/OFF buttons
- Special device power controls (e.g., Zone 2 for EMotiva)

### Media Stack Zone
- **Inputs**: Dropdown selector for input sources
- **Playback**: Media control buttons
- **Tracks**: Track navigation controls

### Volume Zone
- Volume slider (when available)
- Volume up/down buttons
- Mute control

### Navigation Zone
- Directional pad (up/down/left/right)
- OK/Select button
- Auxiliary navigation buttons

### Apps Zone
- Application launcher dropdown
- Quick access to streaming apps

### Screen Zone
- Display mode controls
- Picture settings
- Screen-specific functions

### Pointer Zone
- Trackpad-style cursor control
- Click and drag functionality

## Troubleshooting

### Common Issues
1. **Device Not Responding**: Check connection and power
2. **Actions Not Working**: Verify permissions and parameters
3. **UI Issues**: Clear cache and refresh page

Last updated: ${new Date().toISOString()}
`;
  }

  private generateDeviceClassMarkdown(deviceClass: string, devices: RemoteDeviceStructure[]): string {
    const classDevices = devices.filter(d => d.deviceClass === deviceClass);
    
    return `# ${this.formatClassDisplayName(deviceClass)} - Device Class Documentation

## Overview
This document covers all ${deviceClass} devices in the system.

## Devices
${classDevices.map(device => `- **${device.deviceName}** (\`${device.deviceId}\`)`).join('\n')}

## Remote Control Features
All ${deviceClass} devices support the standard remote control layout with device-specific customizations.

Last updated: ${new Date().toISOString()}
`;
  }

  private countRemoteZoneActions(remoteZones: any[]): number {
    let total = 0;
    
    remoteZones.forEach(zone => {
      if (zone.content) {
        const content = zone.content;
        
        // Count actions in each content type
        if (content.powerButtons) total += content.powerButtons.length;
        if (content.screenActions) total += content.screenActions.length;
        if (content.volumeSlider) total += 1;
        if (content.volumeButtons) total += Object.keys(content.volumeButtons).filter(key => content.volumeButtons[key]).length;
        if (content.navigationCluster) total += Object.keys(content.navigationCluster).filter(key => content.navigationCluster[key]).length;
        if (content.playbackSection && content.playbackSection.actions) total += content.playbackSection.actions.length;
        if (content.tracksSection && content.tracksSection.actions) total += content.tracksSection.actions.length;
        if (content.pointerPad) total += 1;
        if (content.inputsDropdown && content.inputsDropdown.options) total += content.inputsDropdown.options.length;
        if (content.appsDropdown && content.appsDropdown.options) total += content.appsDropdown.options.length;
      }
    });
    
    return total;
  }

  private generateDocumentationSummary(devices: RemoteDeviceStructure[]): DeviceDocumentationSummary {
    return {
      totalDevices: devices.length,
      deviceClasses: this.getUniqueDeviceClasses(devices),
      totalActions: devices.reduce((total, device) => total + this.countRemoteZoneActions(device.remoteZones), 0),
      totalSections: devices.reduce((total, device) => total + device.remoteZones.length, 0),
      generationDate: new Date()
    };
  }

  private groupDevicesByClass(devices: RemoteDeviceStructure[]): Record<string, RemoteDeviceStructure[]> {
    return devices.reduce((acc, device) => {
      if (!acc[device.deviceClass]) {
        acc[device.deviceClass] = [];
      }
      acc[device.deviceClass].push(device);
      return acc;
    }, {} as Record<string, RemoteDeviceStructure[]>);
  }

  private getUniqueDeviceClasses(devices: RemoteDeviceStructure[]): string[] {
    return Array.from(new Set(devices.map(d => d.deviceClass)));
  }

  private formatComponentName(deviceId: string): string {
    return deviceId
      .split('_')
      .map(word => word.charAt(0).toUpperCase() + word.slice(1))
      .join('');
  }

  private formatClassDisplayName(deviceClass: string): string {
    return deviceClass
      .replace(/([a-z])([A-Z])/g, '$1 $2')
      .replace(/([A-Z]+)([A-Z][a-z])/g, '$1 $2');
  }

  private generateChecksum(content: string): string {
    // Simple checksum implementation
    let hash = 0;
    for (let i = 0; i < content.length; i++) {
      const char = content.charCodeAt(i);
      hash = ((hash << 5) - hash) + char;
      hash = hash & hash; // Convert to 32-bit integer
    }
    return Math.abs(hash).toString(16);
  }
} 