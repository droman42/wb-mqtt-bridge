import * as fs from 'fs/promises';
import * as path from 'path';
import { DeviceStructure } from '../../types/ProcessedDevice';

export interface DevicePageEntry {
  id: string;
  name: string;
  deviceClass: string;
  componentName: string;
  route: string;
  filePath: string;
  generatedAt: Date;
  checksum: string;
}

export interface GeneratedFile {
  filepath: string;
  content: string;
  dependencies: string[];
  checksum: string;
  generatedAt: Date;
  sourceHash: string;
}

export interface RouterManifest {
  devices: DevicePageEntry[];
  generatedAt: string;
  apiVersion: string;
  totalDevices: number;
  deviceClasses: string[];
}

export class RouterIntegration {
  async generateRouterManifest(devices: DevicePageEntry[]): Promise<GeneratedFile> {
    const manifest: RouterManifest = {
      devices,
      generatedAt: new Date().toISOString(),
      apiVersion: '1.0',
      totalDevices: devices.length,
      deviceClasses: Array.from(new Set(devices.map(d => d.deviceClass)))
    };

    const routerCode = this.generateRouterCode(devices, manifest);
    
    return {
      filepath: 'src/pages/devices/index.gen.ts',
      content: routerCode,
      dependencies: devices.map(d => `./devices/${d.id}.gen`),
      checksum: this.generateChecksum(routerCode),
      generatedAt: new Date(),
      sourceHash: this.generateChecksum(JSON.stringify(manifest))
    };
  }

  async generateLazyRouterManifest(devices: DevicePageEntry[]): Promise<GeneratedFile> {
    const manifest: RouterManifest = {
      devices,
      generatedAt: new Date().toISOString(),
      apiVersion: '1.0',
      totalDevices: devices.length,
      deviceClasses: Array.from(new Set(devices.map(d => d.deviceClass)))
    };

    const routerCode = this.generateLazyRouterCode(devices, manifest);
    
    return {
      filepath: 'src/pages/devices/lazy-routes.gen.ts',
      content: routerCode,
      dependencies: devices.map(d => `./devices/${d.id}.gen`),
      checksum: this.generateChecksum(routerCode),
      generatedAt: new Date(),
      sourceHash: this.generateChecksum(JSON.stringify(manifest))
    };
  }

  async generateDeviceRegistry(devices: DevicePageEntry[]): Promise<GeneratedFile> {
    const registryCode = `// Auto-generated device registry - DO NOT EDIT
// Generated at: ${new Date().toISOString()}

export interface DeviceRegistryEntry {
  id: string;
  name: string;
  deviceClass: string;
  route: string;
  componentName: string;
  generatedAt: string;
}

export const deviceRegistry: Record<string, DeviceRegistryEntry> = {
${devices.map(device => `  '${device.id}': {
    id: '${device.id}',
    name: '${device.name}',
    deviceClass: '${device.deviceClass}',
    route: '${device.route}',
    componentName: '${device.componentName}',
    generatedAt: '${device.generatedAt.toISOString()}'
  }`).join(',\n')}
};

export const deviceClasses = [
${Array.from(new Set(devices.map(d => d.deviceClass))).map(cls => `  '${cls}'`).join(',\n')}
];

export const deviceRoutes = [
${devices.map(device => `  { path: '${device.route}', deviceId: '${device.id}' }`).join(',\n')}
];

export function getDeviceById(deviceId: string): DeviceRegistryEntry | undefined {
  return deviceRegistry[deviceId];
}

export function getDevicesByClass(deviceClass: string): DeviceRegistryEntry[] {
  return Object.values(deviceRegistry).filter(device => device.deviceClass === deviceClass);
}

export function getAllDeviceIds(): string[] {
  return Object.keys(deviceRegistry);
}

export function getDeviceRoute(deviceId: string): string | undefined {
  return deviceRegistry[deviceId]?.route;
}`;

    return {
      filepath: 'src/pages/devices/registry.gen.ts',
      content: registryCode,
      dependencies: [],
      checksum: this.generateChecksum(registryCode),
      generatedAt: new Date(),
      sourceHash: this.generateChecksum(JSON.stringify(devices))
    };
  }

  async updateExistingRouter(routerFilePath: string, devices: DevicePageEntry[]): Promise<void> {
    try {
      let routerContent = await fs.readFile(routerFilePath, 'utf8');
      
      // Look for generated routes section
      const generatedSectionStart = '// BEGIN GENERATED DEVICE ROUTES';
      const generatedSectionEnd = '// END GENERATED DEVICE ROUTES';
      
      const startIndex = routerContent.indexOf(generatedSectionStart);
      const endIndex = routerContent.indexOf(generatedSectionEnd);
      
      if (startIndex !== -1 && endIndex !== -1) {
        // Replace existing generated section
        const beforeSection = routerContent.substring(0, startIndex);
        const afterSection = routerContent.substring(endIndex + generatedSectionEnd.length);
        
        const generatedSection = this.generateRouterSection(devices);
        
        routerContent = beforeSection + generatedSection + afterSection;
        
        await fs.writeFile(routerFilePath, routerContent, 'utf8');
      } else {
        console.warn(`Could not find generated section markers in ${routerFilePath}`);
      }
    } catch (error) {
      console.error(`Failed to update router at ${routerFilePath}:`, error.message);
    }
  }

  createDevicePageEntry(structure: DeviceStructure, outputPath: string): DevicePageEntry {
    return {
      id: structure.deviceId,
      name: structure.deviceName,
      deviceClass: structure.deviceClass,
      componentName: this.formatComponentName(structure.deviceId),
      route: `/devices/${structure.deviceId}`,
      filePath: outputPath,
      generatedAt: new Date(),
      checksum: this.generateChecksum(structure.deviceId + structure.deviceName)
    };
  }

  async generateNavigationConfig(devices: DevicePageEntry[]): Promise<GeneratedFile> {
    const devicesByClass = this.groupDevicesByClass(devices);
    
    const navConfig = `// Auto-generated navigation configuration - DO NOT EDIT
// Generated at: ${new Date().toISOString()}

export interface NavigationItem {
  label: string;
  path: string;
  icon?: string;
  children?: NavigationItem[];
}

export const deviceNavigation: NavigationItem[] = [
${Object.entries(devicesByClass).map(([deviceClass, classDevices]) => `  {
    label: '${this.formatClassDisplayName(deviceClass)}',
    path: '/devices/${deviceClass.toLowerCase()}',
    children: [
${classDevices.map(device => `      {
        label: '${device.name}',
        path: '${device.route}',
        icon: '${this.getDeviceIcon(device.deviceClass)}'
      }`).join(',\n')}
    ]
  }`).join(',\n')}
];

export function getNavigationForDevice(deviceId: string): NavigationItem | undefined {
  for (const category of deviceNavigation) {
    if (category.children) {
      const device = category.children.find(child => child.path.includes(deviceId));
      if (device) return device;
    }
  }
  return undefined;
}`;

    return {
      filepath: 'src/config/device-navigation.gen.ts',
      content: navConfig,
      dependencies: [],
      checksum: this.generateChecksum(navConfig),
      generatedAt: new Date(),
      sourceHash: this.generateChecksum(JSON.stringify(devices))
    };
  }

  private generateRouterCode(devices: DevicePageEntry[], manifest: RouterManifest): string {
    return `// Auto-generated router manifest - DO NOT EDIT
// Generated at: ${manifest.generatedAt}
// Total devices: ${manifest.totalDevices}
// Device classes: ${manifest.deviceClasses.join(', ')}

import React from 'react';

${devices.map(device => `import ${device.componentName}Page from './devices/${device.id}.gen';`).join('\n')}

export const generatedDevicePages = {
${devices.map(device => `  '${device.id}': ${device.componentName}Page`).join(',\n')}
};

export const devicePageManifest = ${JSON.stringify(manifest, null, 2)};

export const deviceRoutes = [
${devices.map(device => `  {
    path: '${device.route}',
    component: ${device.componentName}Page,
    deviceId: '${device.id}',
    deviceClass: '${device.deviceClass}',
    name: '${device.name}'
  }`).join(',\n')}
];

export function getDeviceComponent(deviceId: string): React.ComponentType | undefined {
  return generatedDevicePages[deviceId];
}

export function getDeviceRoute(deviceId: string): string | undefined {
  const route = deviceRoutes.find(r => r.deviceId === deviceId);
  return route?.path;
}`;
  }

  private generateLazyRouterCode(devices: DevicePageEntry[], manifest: RouterManifest): string {
    return `// Auto-generated lazy router manifest - DO NOT EDIT
// Generated at: ${manifest.generatedAt}
// Total devices: ${manifest.totalDevices}
// Device classes: ${manifest.deviceClasses.join(', ')}

import { lazy } from 'react';

${devices.map(device => `const ${device.componentName}Page = lazy(() => import('./devices/${device.id}.gen'));`).join('\n')}

export const generatedDevicePages = {
${devices.map(device => `  '${device.id}': ${device.componentName}Page`).join(',\n')}
};

export const devicePageManifest = ${JSON.stringify(manifest, null, 2)};

export const lazyDeviceRoutes = [
${devices.map(device => `  {
    path: '${device.route}',
    component: ${device.componentName}Page,
    deviceId: '${device.id}',
    deviceClass: '${device.deviceClass}',
    name: '${device.name}'
  }`).join(',\n')}
];

export function getLazyDeviceComponent(deviceId: string): React.LazyExoticComponent<React.ComponentType> | undefined {
  return generatedDevicePages[deviceId];
}`;
  }

  private generateRouterSection(devices: DevicePageEntry[]): string {
    return `// BEGIN GENERATED DEVICE ROUTES
${devices.map(device => `import ${device.componentName}Page from './devices/${device.id}.gen';`).join('\n')}

const generatedDeviceRoutes = [
${devices.map(device => `  { path: '${device.route}', component: ${device.componentName}Page }`).join(',\n')}
];
// END GENERATED DEVICE ROUTES`;
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

  private getDeviceIcon(deviceClass: string): string {
    const iconMap: Record<string, string> = {
      'WirenboardIRDevice': 'remote-control',
      'LgTv': 'tv',
      'EMotivaXMC2': 'speaker',
      'BroadlinkKitchenHood': 'fan',
      'AppleTVDevice': 'tv'
    };
    
    return iconMap[deviceClass] || 'device';
  }

  private groupDevicesByClass(devices: DevicePageEntry[]): Record<string, DevicePageEntry[]> {
    return devices.reduce((acc, device) => {
      if (!acc[device.deviceClass]) {
        acc[device.deviceClass] = [];
      }
      acc[device.deviceClass].push(device);
      return acc;
    }, {} as Record<string, DevicePageEntry[]>);
  }

  private generateChecksum(content: string): string {
    // Simple checksum using string length and character codes
    let hash = 0;
    for (let i = 0; i < content.length; i++) {
      const char = content.charCodeAt(i);
      hash = ((hash << 5) - hash) + char;
      hash = hash & hash; // Convert to signed 32-bit integer
    }
    return Math.abs(hash).toString(16);
  }
} 