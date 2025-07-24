import { DevicePageGenerator } from '../scripts/generate-device-pages';
import { ErrorHandler, type ErrorContext } from './ErrorHandler';
import { PerformanceMonitor } from './PerformanceMonitor';

export interface BatchResult {
  totalProcessed: number;
  successful: number;
  failed: number;
  skipped: number;
  successRate: number;
  processingTime: number;
  failedDevices: FailedDevice[];
  generatedFiles: string[];
  performance: any;
}

export interface FailedDevice {
  deviceId: string;
  error: string;
  deviceClass?: string;
  action: 'skipped' | 'failed';
}

export interface GenerationResult {
  deviceId: string;
  success: boolean;
  error?: string;
  outputPath?: string;
  deviceClass?: string;
  skipped?: boolean;
}

export interface BatchConfig {
  deviceIds?: string[];
  deviceClasses?: string[];
  maxConcurrency?: number;
  continueOnError?: boolean;
  retryFailures?: boolean;
}

export class BatchProcessor {
  private errorHandler = new ErrorHandler();
  private performanceMonitor = new PerformanceMonitor();
  
  constructor(private generator: DevicePageGenerator) {}
  
  async processDeviceList(deviceIds: string[], config: BatchConfig = {}): Promise<BatchResult> {
    const startTime = Date.now();
    const results: GenerationResult[] = [];
    const maxConcurrency = config.maxConcurrency || 3;
    
    console.log(`🚀 Starting batch processing of ${deviceIds.length} devices...`);
    console.log(`📊 Configuration: max concurrency=${maxConcurrency}, continue on error=${config.continueOnError !== false}`);
    
    // Process devices in batches to avoid overwhelming the API
    for (let i = 0; i < deviceIds.length; i += maxConcurrency) {
      const batch = deviceIds.slice(i, i + maxConcurrency);
      console.log(`\n📦 Processing batch ${Math.floor(i / maxConcurrency) + 1}/${Math.ceil(deviceIds.length / maxConcurrency)}: [${batch.join(', ')}]`);
      
      const batchPromises = batch.map(deviceId => this.processDeviceWithErrorHandling(deviceId));
      const batchResults = await Promise.all(batchPromises);
      
      results.push(...batchResults);
      
      // Check if we should continue after failures
      const batchFailures = batchResults.filter(r => !r.success && !r.skipped);
      if (batchFailures.length > 0 && config.continueOnError === false) {
        console.log(`\n🛑 Stopping batch processing due to failures in current batch`);
        break;
      }
      
      // Small delay between batches to be respectful to the API
      if (i + maxConcurrency < deviceIds.length) {
        await this.delay(500);
      }
    }
    
    return this.summarizeResults(results, Date.now() - startTime);
  }

  async processDeviceListWithStateConfig(
    deviceIds: string[], 
    stateConfigByDeviceClass: Map<string, {
      stateFile?: string; 
      stateClass?: string; 
      stateClassImport?: string;
    }>, 
    config: BatchConfig = {}
  ): Promise<BatchResult> {
    const startTime = Date.now();
    const results: GenerationResult[] = [];
    const maxConcurrency = config.maxConcurrency || 3;
    
    console.log(`🚀 Starting batch processing of ${deviceIds.length} devices...`);
    console.log(`📊 Configuration: max concurrency=${maxConcurrency}, continue on error=${config.continueOnError !== false}`);
    
    // Process devices in batches to avoid overwhelming the API
    for (let i = 0; i < deviceIds.length; i += maxConcurrency) {
      const batch = deviceIds.slice(i, i + maxConcurrency);
      console.log(`\n📦 Processing batch ${Math.floor(i / maxConcurrency) + 1}/${Math.ceil(deviceIds.length / maxConcurrency)}: [${batch.join(', ')}]`);
      
      const batchPromises = batch.map(deviceId => 
        this.processDeviceWithStateConfigAndErrorHandling(deviceId, stateConfigByDeviceClass)
      );
      const batchResults = await Promise.all(batchPromises);
      
      results.push(...batchResults);
      
      // Check if we should continue after failures
      const batchFailures = batchResults.filter(r => !r.success && !r.skipped);
      if (batchFailures.length > 0 && config.continueOnError === false) {
        console.log(`\n🛑 Stopping batch processing due to failures in current batch`);
        break;
      }
      
      // Small delay between batches to be respectful to the API
      if (i + maxConcurrency < deviceIds.length) {
        await this.delay(500);
      }
    }
    
    return this.summarizeResults(results, Date.now() - startTime);
  }
  
  async processAllDevices(config: BatchConfig = {}): Promise<BatchResult> {
    console.log('🔍 Discovering all devices from API...');
    try {
      const devices = await this.discoverDevices();
      console.log(`📋 Found ${devices.length} devices`);
      
      let deviceIds = devices.map(d => d.device_id);
      
      // Filter by device classes if specified
      if (config.deviceClasses && config.deviceClasses.length > 0) {
        const filteredDevices = devices.filter(d => 
          config.deviceClasses!.includes(d.device_class)
        );
        deviceIds = filteredDevices.map(d => d.device_id);
        console.log(`🔎 Filtered to ${deviceIds.length} devices matching classes: [${config.deviceClasses.join(', ')}]`);
      }
      
      return this.processDeviceList(deviceIds, config);
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : String(error);
      console.error('❌ Failed to discover devices:', errorMessage);
      return {
        totalProcessed: 0,
        successful: 0,
        failed: 1,
        skipped: 0,
        successRate: 0,
        processingTime: 0,
        failedDevices: [{ deviceId: 'discovery', error: errorMessage, action: 'failed' }],
        generatedFiles: [],
        performance: this.performanceMonitor.getMetrics()
      };
    }
  }

  async processAllDevicesWithStateConfig(
    stateConfigByDeviceClass: Map<string, {
      stateFile?: string; 
      stateClass?: string; 
      stateClassImport?: string;
    }>,
    config: BatchConfig = {}
  ): Promise<BatchResult> {
    console.log('🔍 Discovering all devices from API...');
    try {
      const devices = await this.discoverDevices();
      console.log(`📋 Found ${devices.length} devices`);
      
      let deviceIds = devices.map(d => d.device_id);
      
      // Filter by device classes if specified
      if (config.deviceClasses && config.deviceClasses.length > 0) {
        const filteredDevices = devices.filter(d => 
          config.deviceClasses!.includes(d.device_class)
        );
        deviceIds = filteredDevices.map(d => d.device_id);
        console.log(`🔎 Filtered to ${deviceIds.length} devices matching classes: [${config.deviceClasses.join(', ')}]`);
      }
      
      return this.processDeviceListWithStateConfig(deviceIds, stateConfigByDeviceClass, config);
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : String(error);
      console.error('❌ Failed to discover devices:', errorMessage);
      return {
        totalProcessed: 0,
        successful: 0,
        failed: 1,
        skipped: 0,
        successRate: 0,
        processingTime: 0,
        failedDevices: [{ deviceId: 'discovery', error: errorMessage, action: 'failed' }],
        generatedFiles: [],
        performance: this.performanceMonitor.getMetrics()
      };
    }
  }
  
  private async processDeviceWithErrorHandling(deviceId: string): Promise<GenerationResult> {
    const timer = this.performanceMonitor.trackGenerationStart(deviceId);
    
    try {
      console.log(`  🔄 Processing ${deviceId}...`);
      const result = await this.generator.generateDevicePage(deviceId);
      
      if (result.success) {
        console.log(`  ✅ ${deviceId} → ${result.outputPath}`);
        timer.complete(true, result.deviceClass || 'unknown');
        return {
          deviceId,
          success: true,
          outputPath: result.outputPath,
          deviceClass: result.deviceClass
        };
      } else {
        // Handle error through error handler
        const error = new Error(result.error || 'Unknown generation error');
        const context: ErrorContext = {
          deviceId,
          deviceClass: result.deviceClass,
          operation: 'device_generation',
          timestamp: new Date()
        };
        
        const recovery = this.errorHandler.handleError(error, context);
        timer.complete(false, result.deviceClass || 'unknown');
        
        if (recovery.action === 'skip') {
          console.log(`  ⏭️  ${deviceId} → ${recovery.message}`);
          return {
            deviceId,
            success: false,
            error: recovery.message,
            skipped: true,
            deviceClass: result.deviceClass
          };
        } else {
          console.log(`  ❌ ${deviceId} → ${recovery.message}`);
          return {
            deviceId,
            success: false,
            error: recovery.message,
            deviceClass: result.deviceClass
          };
        }
      }
    } catch (error) {
      const context: ErrorContext = {
        deviceId,
        operation: 'device_generation',
        timestamp: new Date()
      };
      
      const recovery = this.errorHandler.handleError(error as Error, context);
      timer.complete(false, 'unknown');
      
      console.log(`  💥 ${deviceId} → ${recovery.message}`);
      return {
        deviceId,
        success: false,
        error: recovery.message,
        skipped: recovery.action === 'skip'
      };
    }
  }
  
  private async processDeviceWithStateConfigAndErrorHandling(
    deviceId: string, 
    stateConfigByDeviceClass: Map<string, {
      stateClassImport?: string;
    }>
  ): Promise<GenerationResult> {
    const timer = this.performanceMonitor.trackGenerationStart(deviceId);
    
    try {
      console.log(`  🔄 Processing ${deviceId}...`);
      
      // First, fetch device config to determine device class
      const client = (this.generator as any).client;
      const config = await client.fetchDeviceConfig(deviceId);
      const deviceClass = config.device_class;
      
      // Get state configuration for this device class
      const stateConfig = stateConfigByDeviceClass.get(deviceClass);
      let options: { 
        stateClassImport?: string; 
      } | undefined = undefined;
      
      if (stateConfig && stateConfig.stateClassImport) {
        options = { stateClassImport: stateConfig.stateClassImport };
        console.log(`  📦 Using package import: ${stateConfig.stateClassImport}`);
      }
      
      const result = await this.generator.generateDevicePage(deviceId, options);
      
      if (result.success) {
        console.log(`  ✅ ${deviceId} → ${result.outputPath}`);
        timer.complete(true, result.deviceClass || 'unknown');
        return {
          deviceId,
          success: true,
          outputPath: result.outputPath,
          deviceClass: result.deviceClass
        };
      } else {
        // Handle error through error handler
        const error = new Error(result.error || 'Unknown generation error');
        const context: ErrorContext = {
          deviceId,
          deviceClass: result.deviceClass,
          operation: 'device_generation',
          timestamp: new Date()
        };
        
        const recovery = this.errorHandler.handleError(error, context);
        timer.complete(false, result.deviceClass || 'unknown');
        
        if (recovery.action === 'skip') {
          console.log(`  ⏭️  ${deviceId} → ${recovery.message}`);
          return {
            deviceId,
            success: false,
            error: recovery.message,
            skipped: true,
            deviceClass: result.deviceClass
          };
        } else {
          console.log(`  ❌ ${deviceId} → ${recovery.message}`);
          return {
            deviceId,
            success: false,
            error: recovery.message,
            deviceClass: result.deviceClass
          };
        }
      }
    } catch (error) {
      const context: ErrorContext = {
        deviceId,
        operation: 'device_generation',
        timestamp: new Date()
      };
      
      const recovery = this.errorHandler.handleError(error as Error, context);
      timer.complete(false, 'unknown');
      
      console.log(`  💥 ${deviceId} → ${recovery.message}`);
      return {
        deviceId,
        success: false,
        error: recovery.message,
        skipped: recovery.action === 'skip'
      };
    }
  }
  
  private async discoverDevices(): Promise<Array<{ device_id: string; device_class: string }>> {
    // Check if we're in local mode by testing client type
    const client = (this.generator as any).client;
    
    if (client && typeof client.getAllDeviceIds === 'function') {
      // Local mode: use mapping file to discover devices
      try {
        console.log('📁 Discovering devices from local mapping file...');
        const deviceIds = await client.getAllDeviceIds();
        
        // Get device class for each device ID by fetching config
        const devices: Array<{ device_id: string; device_class: string }> = [];
        for (const deviceId of deviceIds) {
          try {
            const config = await client.fetchDeviceConfig(deviceId);
            devices.push({
              device_id: config.device_id,
              device_class: config.device_class
            });
          } catch (error) {
            const errorMessage = error instanceof Error ? error.message : String(error);
            console.warn(`⚠️  Could not load config for device ${deviceId}: ${errorMessage}`);
            // Skip devices with invalid configs
          }
        }
        
        console.log(`📋 Local discovery found ${devices.length} valid devices`);
        return devices;
      } catch (error) {
        console.error('❌ Local device discovery failed:', (error as Error).message);
        throw error;
      }
    } else {
      // API mode: try to discover via API endpoint
      try {
        const response = await fetch(`${this.generator.getApiBaseUrl()}/devices`);
        if (!response.ok) {
          throw new Error(`Failed to discover devices: ${response.status}`);
        }
        const devices = await response.json() as Array<{ device_id: string; device_class: string }>;
        console.log(`📋 API discovery found ${devices.length} devices`);
        return devices;
      } catch (error) {
        // If discovery endpoint doesn't exist, return empty array
        console.warn('⚠️  Device discovery endpoint not available');
        return [];
      }
    }
  }
  
  private summarizeResults(results: GenerationResult[], processingTime: number): BatchResult {
    const successful = results.filter(r => r.success);
    const failed = results.filter(r => !r.success && !r.skipped);
    const skipped = results.filter(r => r.skipped);
    
    const failedDevices: FailedDevice[] = [
      ...failed.map(f => ({
        deviceId: f.deviceId,
        error: f.error || 'Unknown error',
        deviceClass: f.deviceClass,
        action: 'failed' as const
      })),
      ...skipped.map(s => ({
        deviceId: s.deviceId,
        error: s.error || 'Skipped',
        deviceClass: s.deviceClass,
        action: 'skipped' as const
      }))
    ];
    
    const batchResult: BatchResult = {
      totalProcessed: results.length,
      successful: successful.length,
      failed: failed.length,
      skipped: skipped.length,
      successRate: results.length > 0 ? (successful.length / results.length) * 100 : 0,
      processingTime,
      failedDevices,
      generatedFiles: successful.map(s => s.outputPath!),
      performance: this.performanceMonitor.getMetrics()
    };
    
    this.printBatchSummary(batchResult);
    return batchResult;
  }
  
  private printBatchSummary(result: BatchResult): void {
    const duration = Math.round(result.processingTime / 1000);
    
    console.log(`\n🎯 Batch Processing Complete`);
    console.log(`━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━`);
    console.log(`⏱️  Duration: ${duration}s`);
    console.log(`📊 Total Processed: ${result.totalProcessed}`);
    console.log(`✅ Successful: ${result.successful}`);
    console.log(`❌ Failed: ${result.failed}`);
    console.log(`⏭️  Skipped: ${result.skipped}`);
    console.log(`🎯 Success Rate: ${result.successRate.toFixed(1)}%`);
    
    if (result.failedDevices.length > 0) {
      console.log(`\n❌ Failed/Skipped Devices:`);
      result.failedDevices.forEach(device => {
        const icon = device.action === 'skipped' ? '⏭️ ' : '❌';
        console.log(`  ${icon} ${device.deviceId}: ${device.error}`);
      });
    }
    
    if (result.generatedFiles.length > 0) {
      console.log(`\n✅ Generated Files:`);
      result.generatedFiles.forEach(file => {
        console.log(`  📄 ${file}`);
      });
    }
    
    // Show performance report
    console.log(this.performanceMonitor.generateReport());
  }
  
  private delay(ms: number): Promise<void> {
    return new Promise(resolve => setTimeout(resolve, ms));
  }
} 