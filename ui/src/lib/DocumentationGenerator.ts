import * as fs from 'fs/promises';
import * as path from 'path';
import { DeviceStructure, UISection, ProcessedAction } from '../types/ProcessedDevice';
import { GeneratedFile } from './integration/RouterIntegration';

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
  constructor(private config: DocumentationConfig = {
    includeUsageExamples: true,
    includeStateDocumentation: true,
    includeActionDocumentation: true,
    includeIntegrationGuide: true,
    outputFormat: 'markdown'
  }) {}

  async generateDeviceDocumentation(structure: DeviceStructure): Promise<GeneratedFile> {
    const content = this.generateDeviceMarkdown(structure);
    
    return {
      filepath: `docs/devices/${structure.deviceId}.md`,
      content,
      dependencies: [],
      checksum: this.generateChecksum(content),
      generatedAt: new Date(),
      sourceHash: this.generateChecksum(JSON.stringify(structure))
    };
  }

  async generateSystemDocumentation(devices: DeviceStructure[]): Promise<GeneratedFile> {
    const content = this.generateSystemMarkdown(devices);
    
    return {
      filepath: 'docs/generated-device-system.md',
      content,
      dependencies: [],
      checksum: this.generateChecksum(content),
      generatedAt: new Date(),
      sourceHash: this.generateChecksum(JSON.stringify(devices))
    };
  }

  async generateAPIDocumentation(devices: DeviceStructure[]): Promise<GeneratedFile> {
    const content = this.generateAPIMarkdown(devices);
    
    return {
      filepath: 'docs/device-api-reference.md',
      content,
      dependencies: [],
      checksum: this.generateChecksum(content),
      generatedAt: new Date(),
      sourceHash: this.generateChecksum(JSON.stringify(devices))
    };
  }

  async generateUsageGuide(devices: DeviceStructure[]): Promise<GeneratedFile> {
    const content = this.generateUsageMarkdown(devices);
    
    return {
      filepath: 'docs/device-usage-guide.md',
      content,
      dependencies: [],
      checksum: this.generateChecksum(content),
      generatedAt: new Date(),
      sourceHash: this.generateChecksum(JSON.stringify(devices))
    };
  }

  async generateDeviceClassDocumentation(deviceClass: string, devices: DeviceStructure[]): Promise<GeneratedFile> {
    const classDevices = devices.filter(d => d.deviceClass === deviceClass);
    const content = this.generateDeviceClassMarkdown(deviceClass, classDevices);
    
    return {
      filepath: `docs/device-classes/${deviceClass.toLowerCase()}.md`,
      content,
      dependencies: [],
      checksum: this.generateChecksum(content),
      generatedAt: new Date(),
      sourceHash: this.generateChecksum(JSON.stringify(classDevices))
    };
  }

  private generateDeviceMarkdown(structure: DeviceStructure): string {
    const { deviceId, deviceName, deviceClass, uiSections } = structure;

    return `# ${deviceName} - Generated Device Page

## Overview
- **Device ID**: \`${deviceId}\`
- **Device Class**: \`${deviceClass}\`
- **Generated At**: ${new Date().toISOString()}
- **Component File**: \`src/pages/devices/${deviceId}.gen.tsx\`

## Device Description
This page was automatically generated for the ${deviceName} device. It provides a user interface for controlling and monitoring the device through its available actions and state.

## UI Sections

${uiSections.map(section => this.generateSectionDocumentation(section)).join('\n\n')}

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
- Icons from \`@heroicons/react/24/outline\`

### Component Structure
- Main container with responsive layout
- Device title section
- Action sections organized by groups
- Consistent styling with Tailwind CSS

Last updated: ${new Date().toISOString()}
`;
  }

  private generateSystemMarkdown(devices: DeviceStructure[]): string {
    const summary = this.generateDocumentationSummary(devices);
    const devicesByClass = this.groupDevicesByClass(devices);

    return `# Generated Device System Documentation

## System Overview

This documentation covers the automatically generated device page system for smart home devices.

### Summary Statistics
- **Total Devices**: ${summary.totalDevices}
- **Device Classes**: ${summary.deviceClasses.length}
- **Total Actions**: ${summary.totalActions}
- **Total UI Sections**: ${summary.totalSections}
- **Last Updated**: ${summary.generationDate.toISOString()}

## Supported Device Classes

${Object.entries(devicesByClass).map(([deviceClass, classDevices]) => 
`### ${this.formatClassDisplayName(deviceClass)}
- **Device Count**: ${classDevices.length}
- **Devices**: ${classDevices.map(d => `\`${d.deviceId}\``).join(', ')}
- **Common UI Patterns**: ${this.getClassUIPatterns(classDevices).join(', ')}
`).join('\n')}

## Architecture

### Code Generation Flow
1. **Configuration Fetch**: Device configuration retrieved from API
2. **Structure Analysis**: Device commands analyzed and grouped
3. **UI Pattern Detection**: Appropriate UI components selected
4. **Component Generation**: React component code generated
5. **File Output**: TypeScript files written to \`src/pages/devices/\`

### File Organization
\`\`\`
src/pages/devices/
├── index.gen.ts           # Router manifest
├── registry.gen.ts        # Device registry
├── lazy-routes.gen.ts     # Lazy-loaded routes
└── devices/
    ├── device1.gen.tsx    # Generated device pages
    ├── device2.gen.tsx
    └── ...
\`\`\`

## Development Workflow

### Generating New Device Pages
\`\`\`bash
# Generate single device
node src/scripts/generate-device-pages.ts --device-id=your_device_id

# Generate all devices
node src/scripts/generate-device-pages.ts --batch

# Generate specific device classes
node src/scripts/generate-device-pages.ts --batch --device-classes=LgTv,WirenboardIRDevice
\`\`\`

### Validation and Testing
\`\`\`bash
# Validate generated code
npm run validate:generated-code

# Test component rendering
npm run test:device-pages

# Type checking
npm run type-check
\`\`\`

## Generated Components

${devices.map(device => `### ${device.deviceName}
- **ID**: \`${device.deviceId}\`
- **Class**: \`${device.deviceClass}\`
- **File**: \`${device.deviceId}.gen.tsx\`
- **Route**: \`/devices/${device.deviceId}\`
- **Sections**: ${device.uiSections.length}
- **Actions**: ${device.uiSections.reduce((total, section) => total + section.actions.length, 0)}
`).join('\n')}

## Maintenance

### Regenerating Pages
Device pages should be regenerated when:
- Device configuration changes
- New actions are added
- UI patterns need updates
- Bug fixes are applied to templates

### Customization Guidelines
- Generated files are marked with \`.gen.tsx\` extension
- Manual customizations should be documented
- Consider creating wrapper components for complex customizations
- Test thoroughly after regeneration

Last updated: ${new Date().toISOString()}
`;
  }

  private generateAPIMarkdown(devices: DeviceStructure[]): string {
    const allActions = devices.flatMap(d => 
      d.uiSections.flatMap(s => s.actions)
    );

    return `# Device API Reference

## Overview
This document provides API reference for all generated device components and their actions.

## Device Actions

${devices.map(device => `### ${device.deviceName} (\`${device.deviceId}\`)

${device.uiSections.map(section => `#### ${section.sectionName}

${section.actions.map(action => `##### ${action.displayName}
- **Action Name**: \`${action.actionName}\`
- **Description**: ${action.description}
- **Parameters**: ${action.parameters.length > 0 ? action.parameters.map(p => `\`${p.name}\` (${p.type})`).join(', ') : 'None'}
- **Group**: \`${action.group}\`
- **Icon**: ${action.icon.iconLibrary}/${action.icon.iconName}

\`\`\`typescript
// Usage example
handleAction('${action.actionName}'${action.parameters.length > 0 ? `, { ${action.parameters.map(p => `${p.name}: ${this.getParameterExample(p)}`).join(', ')} }` : ''});
\`\`\`
`).join('\n')}
`).join('\n')}
`).join('\n\n')}

## Component Hooks

### useExecuteDeviceAction
Main hook for executing device actions.

\`\`\`typescript
const executeAction = useExecuteDeviceAction();

executeAction.mutate({
  deviceId: 'your_device_id',
  action: {
    name: 'action_name',
    ...parameters
  }
});
\`\`\`

### useLogStore
Hook for logging user interactions.

\`\`\`typescript
const { addLog } = useLogStore();

addLog({
  level: 'info',
  message: 'Action executed',
  details: { action: 'action_name' }
});
\`\`\`

## UI Component Types

${this.getUniqueComponentTypes(devices).map(componentType => `### ${componentType}
${this.getComponentTypeDescription(componentType)}
`).join('\n')}

Last updated: ${new Date().toISOString()}
`;
  }

  private generateUsageMarkdown(devices: DeviceStructure[]): string {
    return `# Device Usage Guide

## Getting Started

This guide explains how to use the generated device pages for controlling your smart home devices.

## Device Overview

You have ${devices.length} devices configured across ${this.getUniqueDeviceClasses(devices).length} device classes:

${this.getUniqueDeviceClasses(devices).map(deviceClass => `### ${this.formatClassDisplayName(deviceClass)}
${devices.filter(d => d.deviceClass === deviceClass).map(device => `- **${device.deviceName}** (\`${device.deviceId}\`) - [Access Page](/devices/${device.deviceId})`).join('\n')}
`).join('\n')}

## Common Operations

### Basic Device Control
Most devices support these common operations:
1. **Power Control**: Turn devices on/off
2. **Input Selection**: Change device inputs/sources
3. **Volume Control**: Adjust audio levels
4. **Navigation**: Menu and directional controls

### Using Action Buttons
- Click any action button to execute the command
- Actions are organized into logical groups
- Icons indicate the function of each button
- Some actions may require additional parameters

### Parameter-Based Controls
Some devices have controls that accept parameters:

#### Slider Controls
- Used for volume, brightness, temperature
- Drag slider to adjust value
- Real-time feedback shows current setting

#### Input Fields
- Used for text input, channel numbers
- Enter value and press action button
- Validation ensures correct format

## Device-Specific Features

${devices.map(device => `### ${device.deviceName}

${device.uiSections.map(section => `#### ${section.sectionName}
${this.generateSectionUsageGuide(section)}
`).join('\n')}
`).join('\n')}

## Troubleshooting

### Common Issues

#### Device Not Responding
1. Check device connection status
2. Verify device is powered on
3. Check network connectivity
4. Try refreshing the page

#### Actions Not Working
1. Ensure you have proper permissions
2. Check device-specific requirements
3. Verify action parameters are correct
4. Check browser console for errors

#### UI Issues
1. Clear browser cache
2. Refresh the page
3. Check browser compatibility
4. Try different device/screen size

### Getting Help
- Check device documentation
- Review API logs
- Contact system administrator
- Report issues through feedback system

Last updated: ${new Date().toISOString()}
`;
  }

  private generateDeviceClassMarkdown(deviceClass: string, devices: DeviceStructure[]): string {
    return `# ${this.formatClassDisplayName(deviceClass)} - Device Class Documentation

## Overview
This document covers all devices of class \`${deviceClass}\` and their common patterns.

## Device Class Characteristics
- **Class Name**: \`${deviceClass}\`
- **Device Count**: ${devices.length}
- **Common UI Patterns**: ${this.getClassUIPatterns(devices).join(', ')}
- **Typical Sections**: ${this.getCommonSectionTypes(devices).join(', ')}

## Devices in This Class

${devices.map(device => `### ${device.deviceName} (\`${device.deviceId}\`)
- **Sections**: ${device.uiSections.length}
- **Total Actions**: ${device.uiSections.reduce((total, section) => total + section.actions.length, 0)}
- **Route**: \`/devices/${device.deviceId}\`
- [Device Documentation](../devices/${device.deviceId}.md)
`).join('\n')}

## Common UI Patterns

${this.getClassUIPatterns(devices).map(pattern => `### ${pattern}
${this.getUIPatternDescription(pattern, deviceClass)}
`).join('\n')}

## Implementation Details

### Device Handler
File: \`src/lib/deviceHandlers/${deviceClass}Handler.ts\`

### Common Actions
${this.getCommonActions(devices).map(action => `- **${action.displayName}**: ${action.description}`).join('\n')}

### State Management
${deviceClass} devices typically manage these state properties:
${this.getCommonStateProperties(devices).map(prop => `- \`${prop}\`: Device ${prop} status`).join('\n')}

Last updated: ${new Date().toISOString()}
`;
  }

  private generateSectionDocumentation(section: UISection): string {
    return `### ${section.sectionName}
- **Component Type**: \`${section.componentType}\`
- **Actions**: ${section.actions.length}
- **Section ID**: \`${section.sectionId}\`

${section.actions.map(action => `#### ${action.displayName}
- **Action**: \`${action.actionName}\`
- **Description**: ${action.description}
- **Icon**: ${action.icon.iconLibrary}/${action.icon.iconName}
${action.parameters.length > 0 ? `- **Parameters**: ${action.parameters.map(p => `\`${p.name}\` (${p.type})`).join(', ')}` : ''}
`).join('\n')}`;
  }

  private generateSectionUsageGuide(section: UISection): string {
    switch (section.componentType) {
      case 'ButtonGrid':
        return `Grid of action buttons. Click any button to execute the corresponding action.`;
      case 'PointerPad':
        return `Touch/mouse pad for cursor control. Move cursor by dragging, click to select.`;
      case 'SliderControl':
        return `Slider controls for parameter adjustment. Drag sliders to set values.`;
      case 'NavCluster':
        return `Navigation controls with directional buttons and OK/back actions.`;
      default:
        return `Interactive controls for device actions.`;
    }
  }

  private generateDocumentationSummary(devices: DeviceStructure[]): DeviceDocumentationSummary {
    return {
      totalDevices: devices.length,
      deviceClasses: this.getUniqueDeviceClasses(devices),
      totalActions: devices.reduce((total, device) => 
        total + device.uiSections.reduce((sectionTotal, section) => 
          sectionTotal + section.actions.length, 0), 0),
      totalSections: devices.reduce((total, device) => total + device.uiSections.length, 0),
      generationDate: new Date()
    };
  }

  private groupDevicesByClass(devices: DeviceStructure[]): Record<string, DeviceStructure[]> {
    return devices.reduce((acc, device) => {
      if (!acc[device.deviceClass]) {
        acc[device.deviceClass] = [];
      }
      acc[device.deviceClass].push(device);
      return acc;
    }, {} as Record<string, DeviceStructure[]>);
  }

  private getUniqueDeviceClasses(devices: DeviceStructure[]): string[] {
    return Array.from(new Set(devices.map(d => d.deviceClass)));
  }

  private getUniqueComponentTypes(devices: DeviceStructure[]): string[] {
    const types = new Set<string>();
    devices.forEach(device => {
      device.uiSections.forEach(section => {
        types.add(section.componentType);
      });
    });
    return Array.from(types);
  }

  private getClassUIPatterns(devices: DeviceStructure[]): string[] {
    const patterns = new Set<string>();
    devices.forEach(device => {
      device.uiSections.forEach(section => {
        patterns.add(section.componentType);
      });
    });
    return Array.from(patterns);
  }

  private getCommonSectionTypes(devices: DeviceStructure[]): string[] {
    const sectionTypes = new Set<string>();
    devices.forEach(device => {
      device.uiSections.forEach(section => {
        sectionTypes.add(section.sectionName);
      });
    });
    return Array.from(sectionTypes);
  }

  private getCommonActions(devices: DeviceStructure[]): ProcessedAction[] {
    // Return first few actions as examples
    const allActions = devices.flatMap(d => d.uiSections.flatMap(s => s.actions));
    return allActions.slice(0, 5);
  }

  private getCommonStateProperties(devices: DeviceStructure[]): string[] {
    return ['isConnected', 'lastUpdated', 'deviceStatus'];
  }

  private getComponentTypeDescription(componentType: string): string {
    const descriptions = {
      'ButtonGrid': 'Grid layout of action buttons for simple commands',
      'PointerPad': 'Touch/mouse control pad for cursor movement',
      'SliderControl': 'Slider controls for parameter-based adjustments',
      'NavCluster': 'Directional navigation controls with OK/back buttons'
    };
    return descriptions[componentType] || 'Custom UI component';
  }

  private getUIPatternDescription(pattern: string, deviceClass: string): string {
    return `${pattern} components are used in ${deviceClass} devices for specific interaction patterns.`;
  }

  private getParameterExample(param: any): string {
    switch (param.type) {
      case 'number':
      case 'range':
        return '0';
      case 'string':
        return "'value'";
      case 'boolean':
        return 'true';
      default:
        return 'null';
    }
  }

  private formatComponentName(deviceId: string): string {
    return deviceId
      .split(/[-_]/)
      .map(part => part.charAt(0).toUpperCase() + part.slice(1).toLowerCase())
      .join('');
  }

  private formatClassDisplayName(deviceClass: string): string {
    return deviceClass
      .replace(/([A-Z])/g, ' $1')
      .replace(/^./, str => str.toUpperCase())
      .trim();
  }

  private generateChecksum(content: string): string {
    let hash = 0;
    for (let i = 0; i < content.length; i++) {
      const char = content.charCodeAt(i);
      hash = ((hash << 5) - hash) + char;
      hash = hash & hash;
    }
    return Math.abs(hash).toString(16);
  }
} 