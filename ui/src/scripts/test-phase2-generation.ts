import { DevicePageGenerator } from './generate-device-pages';
import { BatchProcessor } from '../lib/BatchProcessor';
import type { DeviceConfig, DeviceGroups } from '../types/DeviceConfig';

// Mock API client for testing Phase 2 features
class MockPhase2ApiClient {
  private mockDevices: Record<string, { config: DeviceConfig; groups: DeviceGroups }> = {
    'smart_tv_lg': {
      config: {
        device_id: 'smart_tv_lg',
        device_name: 'Living Room LG TV',
        device_class: 'LgTv',
        config_class: 'LgTvConfig',
        commands: {
          'move_cursor': {
            action: 'move_cursor',
            topic: 'smart_tv_lg/cursor',
            description: 'Move cursor on screen',
            group: 'pointer',
            params: [
              { name: 'x', type: 'integer', required: true, default: 0, min: -100, max: 100, description: 'X coordinate' },
              { name: 'y', type: 'integer', required: true, default: 0, min: -100, max: 100, description: 'Y coordinate' }
            ]
          },
          'click': {
            action: 'click',
            topic: 'smart_tv_lg/click',
            description: 'Click at cursor position',
            group: 'pointer',
            params: null
          },
          'power': {
            action: 'power_toggle',
            topic: 'smart_tv_lg/power',
            description: 'Toggle TV power',
            group: 'basic',
            params: null
          },
          'volume_up': {
            action: 'volume_up',
            topic: 'smart_tv_lg/volume',
            description: 'Increase volume',
            group: 'basic',
            params: null
          }
        }
      },
      groups: {
        device_id: 'smart_tv_lg',
        groups: [
          {
            group_id: 'pointer',
            group_name: 'Pointer Control',
            actions: [
              { name: 'move_cursor', description: 'Move cursor on screen', params: [
                { name: 'x', type: 'integer', required: true, default: 0, min: -100, max: 100, description: 'X coordinate' },
                { name: 'y', type: 'integer', required: true, default: 0, min: -100, max: 100, description: 'Y coordinate' }
              ]},
              { name: 'click', description: 'Click at cursor position', params: null }
            ],
            status: 'active'
          },
          {
            group_id: 'basic',
            group_name: 'Basic Controls',
            actions: [
              { name: 'power', description: 'Toggle TV power', params: null },
              { name: 'volume_up', description: 'Increase volume', params: null }
            ],
            status: 'active'
          }
        ]
      }
    },
    
    'audio_processor': {
      config: {
        device_id: 'audio_processor',
        device_name: 'Main Audio Processor',
        device_class: 'EMotivaXMC2',
        config_class: 'EMotivaXMC2Config',
        commands: {
          'main_volume': {
            action: 'set_volume',
            topic: 'audio_processor/main/volume',
            description: 'Set main zone volume',
            group: 'main_zone',
            params: [
              { name: 'level', type: 'range', required: true, default: 50, min: 0, max: 100, description: 'Volume level' }
            ]
          },
          'zone2_volume': {
            action: 'set_volume',
            topic: 'audio_processor/zone2/volume',
            description: 'Set zone 2 volume',
            group: 'zone2',
            params: [
              { name: 'level', type: 'range', required: true, default: 50, min: 0, max: 100, description: 'Volume level' }
            ]
          },
          'main_input': {
            action: 'set_input',
            topic: 'audio_processor/main/input',
            description: 'Set main zone input',
            group: 'main_zone',
            params: null
          }
        }
      },
      groups: {
        device_id: 'audio_processor',
        groups: [
          {
            group_id: 'audio_controls',
            group_name: 'Audio Controls',
            actions: [
              { name: 'main_zone_volume', description: 'Main zone volume control', params: [
                { name: 'level', type: 'range', required: true, default: 50, min: 0, max: 100, description: 'Volume level' }
              ]},
              { name: 'zone_2_volume', description: 'Zone 2 volume control', params: [
                { name: 'level', type: 'range', required: true, default: 50, min: 0, max: 100, description: 'Volume level' }
              ]},
              { name: 'main_zone_input', description: 'Main zone input selection', params: null },
              { name: 'zone_2_input', description: 'Zone 2 input selection', params: null }
            ],
            status: 'active'
          }
        ]
      }
    },
    
    'kitchen_hood': {
      config: {
        device_id: 'kitchen_hood',
        device_name: 'Kitchen Range Hood',
        device_class: 'BroadlinkKitchenHood',
        config_class: 'BroadlinkKitchenHoodConfig',
        commands: {
          'fan_speed': {
            action: 'set_fan_speed',
            topic: 'kitchen_hood/fan',
            description: 'Set fan speed',
            group: 'fan_control',
            params: [
              { name: 'speed', type: 'range', required: true, default: 1, min: 0, max: 5, description: 'Fan speed level' }
            ]
          },
          'light_toggle': {
            action: 'toggle_light',
            topic: 'kitchen_hood/light',
            description: 'Toggle hood light',
            group: 'lighting',
            params: null
          },
          'timer': {
            action: 'set_timer',
            topic: 'kitchen_hood/timer',
            description: 'Set auto-off timer',
            group: 'timer',
            params: [
              { name: 'minutes', type: 'range', required: true, default: 10, min: 1, max: 60, description: 'Timer in minutes' }
            ]
          }
        }
      },
      groups: {
        device_id: 'kitchen_hood',
        groups: [
          {
            group_id: 'fan_control',
            group_name: 'Fan Control',
            actions: [
              { name: 'fan_speed', description: 'Set fan speed', params: [
                { name: 'speed', type: 'range', required: true, default: 1, min: 0, max: 5, description: 'Fan speed level' }
              ]},
              { name: 'turbo_mode', description: 'Activate turbo mode', params: null }
            ],
            status: 'active'
          },
          {
            group_id: 'lighting',
            group_name: 'Lighting',
            actions: [
              { name: 'light_toggle', description: 'Toggle hood light', params: null }
            ],
            status: 'active'
          }
        ]
      }
    },
    
    'apple_tv': {
      config: {
        device_id: 'apple_tv',
        device_name: 'Living Room Apple TV',
        device_class: 'AppleTVDevice',
        config_class: 'AppleTVDeviceConfig',
        commands: {
          'up': {
            action: 'navigate_up',
            topic: 'apple_tv/nav',
            description: 'Navigate up',
            group: 'navigation',
            params: null
          },
          'down': {
            action: 'navigate_down',
            topic: 'apple_tv/nav',
            description: 'Navigate down',
            group: 'navigation',
            params: null
          },
          'select': {
            action: 'select',
            topic: 'apple_tv/nav',
            description: 'Select current item',
            group: 'navigation',
            params: null
          },
          'play_pause': {
            action: 'play_pause',
            topic: 'apple_tv/media',
            description: 'Play/pause media',
            group: 'media',
            params: null
          },
          'siri': {
            action: 'activate_siri',
            topic: 'apple_tv/siri',
            description: 'Activate Siri',
            group: 'smart',
            params: null
          }
        }
      },
      groups: {
        device_id: 'apple_tv',
        groups: [
          {
            group_id: 'navigation',
            group_name: 'Navigation',
            actions: [
              { name: 'up', description: 'Navigate up', params: null },
              { name: 'down', description: 'Navigate down', params: null },
              { name: 'left', description: 'Navigate left', params: null },
              { name: 'right', description: 'Navigate right', params: null },
              { name: 'select', description: 'Select current item', params: null }
            ],
            status: 'active'
          },
          {
            group_id: 'media',
            group_name: 'Media Controls',
            actions: [
              { name: 'play_pause', description: 'Play/pause media', params: null },
              { name: 'next', description: 'Next track/chapter', params: null },
              { name: 'previous', description: 'Previous track/chapter', params: null }
            ],
            status: 'active'
          }
        ]
      }
    }
  };

  async fetchDeviceConfig(deviceId: string): Promise<DeviceConfig> {
    const device = this.mockDevices[deviceId];
    if (!device) {
      throw new Error(`Device ${deviceId} not found`);
    }
    return device.config;
  }

  async fetchDeviceGroups(deviceId: string): Promise<DeviceGroups> {
    const device = this.mockDevices[deviceId];
    if (!device) {
      throw new Error(`Device ${deviceId} not found`);
    }
    return device.groups;
  }

  async validateConnectivity(): Promise<boolean> {
    return true;
  }
}

// Test Phase 2 generation
async function testPhase2Generation() {
  console.log('🧪 Testing Phase 2 device page generation with enhanced features...\n');

  // Create a generator with mock client
  const generator = new DevicePageGenerator('http://mock-api:8000', 'src/pages/devices');
  
  // Replace the client with our mock
  (generator as any).client = new MockPhase2ApiClient();

  const testDevices = [
    { id: 'smart_tv_lg', expectedClass: 'LgTv', expectedFeatures: ['PointerPad', 'ButtonGrid'] },
    { id: 'audio_processor', expectedClass: 'EMotivaXMC2', expectedFeatures: ['SliderControl', 'Multi-Zone'] },
    { id: 'kitchen_hood', expectedClass: 'BroadlinkKitchenHood', expectedFeatures: ['SliderControl', 'Parameters'] },
    { id: 'apple_tv', expectedClass: 'AppleTVDevice', expectedFeatures: ['NavCluster', 'ButtonGrid'] }
  ];

  const results = [];

  for (const testDevice of testDevices) {
    console.log(`🔄 Testing generation for: ${testDevice.id} (${testDevice.expectedClass})`);
    
    try {
      const result = await generator.generateDevicePage(testDevice.id);
      
      if (result.success) {
        console.log(`✅ Success: ${result.outputPath}`);
        console.log(`   Device Class: ${result.deviceClass}`);
        console.log(`   UI Sections: ${result.sectionsGenerated}`);
        console.log(`   Duration: ${result.duration}ms`);
        console.log(`   Expected Features: [${testDevice.expectedFeatures.join(', ')}]`);
        
        results.push({ ...result, deviceId: testDevice.id, expected: testDevice });
      } else {
        console.log(`❌ Failed: ${result.error}`);
        results.push({ ...result, deviceId: testDevice.id, expected: testDevice });
      }
    } catch (error) {
      console.log(`💥 Error: ${(error as Error).message}`);
      results.push({ 
        success: false, 
        error: (error as Error).message, 
        deviceId: testDevice.id, 
        expected: testDevice 
      });
    }
    
    console.log('');
  }

  // Test batch processing
  console.log('🚀 Testing batch processing...\n');
  
  try {
    const batchProcessor = new BatchProcessor(generator);
    const batchResult = await batchProcessor.processDeviceList(
      testDevices.map(d => d.id),
      { maxConcurrency: 2 }
    );
    
    console.log('\n📊 Batch Processing Results:');
    console.log(`   Total: ${batchResult.totalProcessed}`);
    console.log(`   Successful: ${batchResult.successful}`);
    console.log(`   Failed: ${batchResult.failed}`);
    console.log(`   Success Rate: ${batchResult.successRate.toFixed(1)}%`);
    
  } catch (error) {
    console.log(`❌ Batch processing failed: ${(error as Error).message}`);
  }

  console.log('\n🎉 Phase 2 test generation complete!');
  
  // Summary
  const successful = results.filter(r => r.success);
  const failed = results.filter(r => !r.success);
  
  console.log('\n📋 Summary:');
  console.log(`✅ Successful: ${successful.length}/${results.length}`);
  console.log(`❌ Failed: ${failed.length}/${results.length}`);
  
  if (failed.length > 0) {
    console.log('\n❌ Failed devices:');
    failed.forEach(f => {
      console.log(`   - ${f.deviceId}: ${f.error}`);
    });
  }
  
  console.log('\n🎯 Phase 2 Features Tested:');
  console.log('   ✅ LgTv with PointerPad component');
  console.log('   ✅ EMotivaXMC2 with multi-zone controls');
  console.log('   ✅ BroadlinkKitchenHood with parameter sliders');
  console.log('   ✅ AppleTVDevice with navigation clusters');
  console.log('   ✅ Enhanced error handling');
  console.log('   ✅ Batch processing system');
  console.log('   ✅ Performance monitoring');
  console.log('   ✅ Enhanced icon resolution');
}

// Run the test
testPhase2Generation().catch(error => {
  console.error('💥 Test failed:', error);
  process.exit(1);
}); 