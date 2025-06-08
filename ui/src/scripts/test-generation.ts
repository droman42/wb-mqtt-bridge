import { DevicePageGenerator } from './generate-device-pages';
import { DeviceConfigurationClient } from '../lib/DeviceConfigurationClient';
import type { DeviceConfig, DeviceGroups } from '../types/DeviceConfig';

// Mock API client that returns test data
class MockDeviceConfigurationClient extends DeviceConfigurationClient {
  constructor() {
    super('mock://localhost');
  }

  async validateConnectivity(): Promise<boolean> {
    return true;
  }

  async fetchDeviceConfig(deviceId: string): Promise<DeviceConfig> {
    return {
      device_id: deviceId,
      device_name: `Test ${deviceId.replace('_', ' ').split(' ').map(w => w[0].toUpperCase() + w.slice(1)).join(' ')}`,
      device_class: 'WirenboardIRDevice',
      config_class: 'WirenboardIRConfig',
      commands: {
        power_on: {
          action: 'power_on',
          topic: `${deviceId}/cmd`,
          description: 'Turn device on',
          group: 'power',
          params: null
        },
        power_off: {
          action: 'power_off', 
          topic: `${deviceId}/cmd`,
          description: 'Turn device off',
          group: 'power',
          params: null
        },
        nav_up: {
          action: 'nav_up',
          topic: `${deviceId}/cmd`,
          description: 'Navigate up',
          group: 'navigation',
          params: null
        },
        nav_down: {
          action: 'nav_down',
          topic: `${deviceId}/cmd`, 
          description: 'Navigate down',
          group: 'navigation',
          params: null
        },
        nav_left: {
          action: 'nav_left',
          topic: `${deviceId}/cmd`,
          description: 'Navigate left',
          group: 'navigation',
          params: null
        },
        nav_right: {
          action: 'nav_right',
          topic: `${deviceId}/cmd`,
          description: 'Navigate right',
          group: 'navigation',
          params: null
        },
        nav_ok: {
          action: 'nav_ok',
          topic: `${deviceId}/cmd`,
          description: 'Select/OK',
          group: 'navigation',
          params: null
        }
      }
    };
  }

  async fetchDeviceGroups(deviceId: string): Promise<DeviceGroups> {
    return {
      device_id: deviceId,
      groups: [
        {
          group_id: 'power',
          group_name: 'Power Control',
          status: 'active',
          actions: [
            {
              name: 'power_on',
              description: 'Turn device on',
              params: null
            },
            {
              name: 'power_off',
              description: 'Turn device off',
              params: null
            }
          ]
        },
        {
          group_id: 'navigation',
          group_name: 'Navigation',
          status: 'active',
          actions: [
            {
              name: 'nav_up',
              description: 'Navigate up',
              params: null
            },
            {
              name: 'nav_down',
              description: 'Navigate down',
              params: null
            },
            {
              name: 'nav_left',
              description: 'Navigate left',
              params: null
            },
            {
              name: 'nav_right',
              description: 'Navigate right',
              params: null
            },
            {
              name: 'nav_ok',
              description: 'Select/OK',
              params: null
            }
          ]
        }
      ]
    };
  }
}

async function testGeneration() {
  console.log('🧪 Testing Phase 1 device page generation with mock data...\n');

  // Create a generator with mock client
  const generator = new DevicePageGenerator('mock://localhost', 'src/pages/devices');
  // Replace the client with our mock
  (generator as any).client = new MockDeviceConfigurationClient();

  const testDevices = ['living_room_tv', 'bedroom_soundbar', 'office_projector'];

  for (const deviceId of testDevices) {
    console.log(`🔄 Testing generation for: ${deviceId}`);
    
    try {
      const result = await generator.generateDevicePage(deviceId);
      
      if (result.success) {
        console.log(`✅ Success: ${result.outputPath}`);
        console.log(`   Device Class: ${result.deviceClass}`);
        console.log(`   UI Sections: ${result.sectionsGenerated}`);
        console.log(`   Duration: ${result.duration}ms\n`);
      } else {
        console.log(`❌ Failed: ${result.error}\n`);
      }
    } catch (error) {
      console.error(`💥 Error: ${error instanceof Error ? error.message : String(error)}\n`);
    }
  }

  console.log('🎉 Test generation complete!');
}

// Run test if this file is executed directly
// Note: In Node.js with tsx, the file check is handled differently
testGeneration().catch(console.error); 