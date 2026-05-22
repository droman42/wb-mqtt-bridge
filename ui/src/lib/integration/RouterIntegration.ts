import * as fs from 'fs/promises';
import type { RemoteDeviceStructure } from '../../types/RemoteControlLayout';

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
  async generateRouterManifest(entries: DevicePageEntry[]): Promise<GeneratedFile> {
    // Separate devices and scenarios
    const devices = entries.filter(entry => entry.deviceClass !== 'ScenarioDevice');
    const scenarios = entries.filter(entry => entry.deviceClass === 'ScenarioDevice');
    
    // Generate device router manifest
    if (devices.length > 0) {
      const deviceManifest: RouterManifest = {
        devices,
        generatedAt: new Date().toISOString(),
        apiVersion: '1.0',
        totalDevices: devices.length,
        deviceClasses: Array.from(new Set(devices.map(d => d.deviceClass)))
      };

      const deviceRouterCode = this.generateRouterCode(devices, deviceManifest, 'devices');
      
      await fs.writeFile('src/pages/devices/index.gen.ts', deviceRouterCode, 'utf8');
      console.log(`✅ Generated device router: src/pages/devices/index.gen.ts (${devices.length} devices)`);
    }
    
    // Generate scenario router manifest
    if (scenarios.length > 0) {
      const scenarioManifest: RouterManifest = {
        devices: scenarios, // Keep same interface but these are scenarios
        generatedAt: new Date().toISOString(),
        apiVersion: '1.0',
        totalDevices: scenarios.length,
        deviceClasses: Array.from(new Set(scenarios.map(s => s.deviceClass)))
      };

      const scenarioRouterCode = this.generateRouterCode(scenarios, scenarioManifest, 'scenarios');
      
      // Ensure scenarios directory exists
      await fs.mkdir('src/pages/scenarios', { recursive: true });
      await fs.writeFile('src/pages/scenarios/index.gen.ts', scenarioRouterCode, 'utf8');
      console.log(`✅ Generated scenario router: src/pages/scenarios/index.gen.ts (${scenarios.length} scenarios)`);
    }
    
    // Return combined manifest for backwards compatibility
    const combinedManifest: RouterManifest = {
      devices: entries,
      generatedAt: new Date().toISOString(),
      apiVersion: '1.0',
      totalDevices: entries.length,
      deviceClasses: Array.from(new Set(entries.map(d => d.deviceClass)))
    };

    const combinedRouterCode = this.generateRouterCode(devices, combinedManifest, 'devices');
    
    return {
      filepath: 'src/pages/devices/index.gen.ts',
      content: combinedRouterCode,
      dependencies: devices.map(d => `./devices/${d.id}.gen`),
      checksum: this.generateChecksum(combinedRouterCode),
      generatedAt: new Date(),
      sourceHash: this.generateChecksum(JSON.stringify(combinedManifest))
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
      const errorMessage = error instanceof Error ? error.message : String(error);
      console.error(`Failed to update router at ${routerFilePath}:`, errorMessage);
    }
  }

  createDevicePageEntry(structure: RemoteDeviceStructure, outputPath: string): DevicePageEntry {
    const isScenario = structure.deviceClass === 'ScenarioDevice';
    const routePrefix = isScenario ? '/scenario' : '/devices';
    
    return {
      id: structure.deviceId,
      name: structure.deviceName,
      deviceClass: structure.deviceClass,
      componentName: this.formatComponentName(structure.deviceId),
      route: `${routePrefix}/${structure.deviceId}`,
      filePath: outputPath,
      generatedAt: new Date(),
      checksum: this.generateChecksum(structure.deviceId + structure.deviceName)
    };
  }



  private generateRouterCode(devices: DevicePageEntry[], manifest: RouterManifest, type: 'devices' | 'scenarios' = 'devices'): string {
    const entityType = type === 'scenarios' ? 'scenario' : 'device';
    const entityTypePlural = type === 'scenarios' ? 'scenarios' : 'devices';
    const getterFunctionName = type === 'scenarios' ? 'getScenarioComponent' : 'getDeviceComponent';
    const exportName = type === 'scenarios' ? 'generatedScenarioPages' : 'generatedDevicePages';
    const manifestName = type === 'scenarios' ? 'scenarioPageManifest' : 'devicePageManifest';
    
    return `// Auto-generated ${entityType} router manifest - DO NOT EDIT
// Generated at: ${manifest.generatedAt}
// Total ${entityTypePlural}: ${manifest.totalDevices}
// Device classes: ${manifest.deviceClasses.join(', ')}

import React from 'react';

${devices.map(device => `import ${device.componentName}Page from './${device.id}.gen';`).join('\n')}

export const ${exportName}: Record<string, React.ComponentType> = {
${devices.map(device => `  '${device.id}': ${device.componentName}Page`).join(',\n')}
};

export const ${manifestName} = ${JSON.stringify(manifest, null, 2)};

export const ${entityType}Routes = [
${devices.map(device => `  {
    path: '${device.route}',
    component: ${device.componentName}Page,
    deviceId: '${device.id}',
    deviceClass: '${device.deviceClass}',
    name: '${device.name}'
  }`).join(',\n')}
];

export function ${getterFunctionName}(${entityType}Id: string): React.ComponentType | undefined {
  return ${exportName}[${entityType}Id];
}

export function get${entityType.charAt(0).toUpperCase() + entityType.slice(1)}Route(${entityType}Id: string): string | undefined {
  const route = ${entityType}Routes.find(r => r.deviceId === ${entityType}Id);
  return route?.path;
}`;
  }

  private generateLazyRouterCode(devices: DevicePageEntry[], manifest: RouterManifest): string {
    return `// Auto-generated lazy router manifest - DO NOT EDIT
// Generated at: ${manifest.generatedAt}
// Total devices: ${manifest.totalDevices}
// Device classes: ${manifest.deviceClasses.join(', ')}

import { lazy } from 'react';

${devices.map(device => `const ${device.componentName}Page = lazy(() => import('./${device.id}.gen'));`).join('\n')}

export const generatedDevicePages: Record<string, React.LazyExoticComponent<React.ComponentType>> = {
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
${devices.map(device => `import ${device.componentName}Page from './${device.id}.gen';`).join('\n')}

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

  async readExistingRouterManifest(): Promise<DevicePageEntry[]> {
    const routerPath = 'src/pages/devices/index.gen.ts';
    
    try {
      const routerContent = await fs.readFile(routerPath, 'utf8');
      
      // Extract the manifest JSON from the file
      const manifestMatch = routerContent.match(/export const devicePageManifest = ({[\s\S]*?});/);
      if (manifestMatch) {
        const manifestJson = manifestMatch[1];
        const manifest = JSON.parse(manifestJson) as RouterManifest;
        
        // Convert manifest devices back to DevicePageEntry format
        return manifest.devices.map(device => ({
          id: device.id,
          name: device.name,
          deviceClass: device.deviceClass,
          componentName: device.componentName,
          route: device.route,
          filePath: device.filePath,
          generatedAt: new Date(device.generatedAt),
          checksum: device.checksum
        }));
      }
    } catch (error) {
      // File doesn't exist or can't be read - that's fine for first generation
      const errorMessage = error instanceof Error ? error.message : String(error);
      console.log(`📝 No existing router manifest found (${errorMessage})`);
    }
    
    return [];
  }

  mergeDeviceEntries(existingDevices: DevicePageEntry[], newDevice: DevicePageEntry): DevicePageEntry[] {
    // Filter out any existing entry with the same device ID
    const filteredExisting = existingDevices.filter(device => device.id !== newDevice.id);
    
    // Add the new device entry
    const mergedDevices = [...filteredExisting, newDevice];
    
    // Sort by device ID for consistent output
    return mergedDevices.sort((a, b) => a.id.localeCompare(b.id));
  }

  async generateIncrementalRouterManifest(newDevice: DevicePageEntry): Promise<GeneratedFile> {
    console.log(`🔄 Reading existing router manifest...`);
    const existingDevices = await this.readExistingRouterManifest();
    
    console.log(`📋 Found ${existingDevices.length} existing device(s)`);
    if (existingDevices.length > 0) {
      console.log(`   Existing: ${existingDevices.map(d => d.id).join(', ')}`);
    }
    
    const mergedDevices = this.mergeDeviceEntries(existingDevices, newDevice);
    console.log(`✅ Merged devices: ${mergedDevices.map(d => d.id).join(', ')}`);
    
    // Use the existing generateRouterManifest method with merged devices
    return this.generateRouterManifest(mergedDevices);
  }

  async generateIncrementalRouterFiles(newDevice: DevicePageEntry): Promise<void> {
    console.log('🗺️ Generating router manifest...');
    const routerManifest = await this.generateIncrementalRouterManifest(newDevice);
    await fs.writeFile(routerManifest.filepath, routerManifest.content, 'utf8');
    console.log(`✅ Generated router manifest: ${routerManifest.filepath}`);
  }
} 