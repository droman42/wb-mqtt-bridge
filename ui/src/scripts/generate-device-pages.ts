import { DeviceConfigurationClient } from '../lib/DeviceConfigurationClient';
import { WirenboardIRHandler } from '../lib/deviceHandlers/WirenboardIRHandler';
import { LgTvHandler } from '../lib/deviceHandlers/LgTvHandler';
import { EMotivaXMC2Handler } from '../lib/deviceHandlers/EMotivaXMC2Handler';
import { BroadlinkKitchenHoodHandler } from '../lib/deviceHandlers/BroadlinkKitchenHoodHandler';
import { AppleTVDeviceHandler } from '../lib/deviceHandlers/AppleTVDeviceHandler';
import { DevicePageTemplate } from '../lib/generators/DevicePageTemplate';
import { DataValidator } from '../lib/DataValidator';
import { BatchProcessor } from '../lib/BatchProcessor';
import { CodeValidator } from '../lib/validation/CodeValidator';
import { ComponentValidator } from '../lib/validation/ComponentValidator';
import { StateTypeGenerator } from '../lib/StateTypeGenerator';
import { RouterIntegration } from '../lib/integration/RouterIntegration';
import { DocumentationGenerator } from '../lib/DocumentationGenerator';
import type { DeviceConfig, DeviceGroups } from '../types/DeviceConfig';
import type { DeviceStructure } from '../types/ProcessedDevice';
import * as fs from 'fs/promises';
import * as path from 'path';

interface GenerationResult {
  success: boolean;
  outputPath?: string;
  deviceClass?: string;
  sectionsGenerated?: number;
  duration: number;
  error?: string;
  deviceId: string;
}

export class DevicePageGenerator {
  private client: DeviceConfigurationClient;
  private validator: DataValidator;
  private outputDir: string;
  private handlers: Map<string, any>;
  private apiBaseUrl: string;
  private codeValidator: CodeValidator;
  private componentValidator: ComponentValidator;
  private stateGenerator: StateTypeGenerator;
  private routerIntegration: RouterIntegration;
  private docGenerator: DocumentationGenerator;

  constructor(apiBaseUrl: string, outputDir: string) {
    this.apiBaseUrl = apiBaseUrl;
    this.client = new DeviceConfigurationClient(apiBaseUrl);
    this.validator = new DataValidator();
    this.outputDir = outputDir;
    this.handlers = new Map<string, any>([
      ['WirenboardIRDevice', new WirenboardIRHandler()],
      ['LgTv', new LgTvHandler()],
      ['EMotivaXMC2', new EMotivaXMC2Handler()],
      ['BroadlinkKitchenHood', new BroadlinkKitchenHoodHandler()],
      ['AppleTVDevice', new AppleTVDeviceHandler()]
    ]);
    
    // Phase 3 components
    this.codeValidator = new CodeValidator();
    this.componentValidator = new ComponentValidator();
    this.stateGenerator = new StateTypeGenerator();
    this.routerIntegration = new RouterIntegration();
    this.docGenerator = new DocumentationGenerator();
  }
  
  async generateDevicePage(deviceId: string, options?: { stateFile?: string; stateClass?: string }): Promise<GenerationResult> {
    console.log(`🔄 Generating page for device: ${deviceId}`);
    const startTime = Date.now();
    
    try {
      // Test API connectivity first
      const isApiAvailable = await this.client.validateConnectivity();
      if (!isApiAvailable) {
        throw new Error('API is not available. Please check if the backend is running.');
      }
      
      console.log('✅ API connectivity confirmed');
      
      // Fetch device data
      console.log('📡 Fetching device configuration...');
      const [config, groups] = await Promise.all([
        this.client.fetchDeviceConfig(deviceId),
        this.client.fetchDeviceGroups(deviceId)
      ]);
      
      console.log(`📋 Found ${Object.keys(config.commands || {}).length} commands and ${groups.groups?.length || 0} groups`);
      
      // Validate data
      const validatedConfig = this.validator.validateDeviceConfig(config);
      console.log(`✅ Configuration validated for device class: ${validatedConfig.device_class}`);
      
      // Get device handler
      const handler = this.handlers.get(validatedConfig.device_class);
      if (!handler) {
        throw new Error(`Unsupported device class: ${validatedConfig.device_class}. Currently supported: ${Array.from(this.handlers.keys()).join(', ')}`);
      }
      
      console.log(`🔧 Using ${handler.deviceClass} handler`);
      
      // Process device structure
      const structure: DeviceStructure = handler.analyzeStructure(validatedConfig, groups);
      console.log(`📊 Generated ${structure.uiSections.length} UI sections`);
      
      // Generate Python state types if requested
      let customStateInterface: string | null = null;
      if (options?.stateFile && options?.stateClass) {
        try {
          console.log(`🐍 Generating TypeScript state from Python: ${options.stateFile}::${options.stateClass}`);
          const stateDefinition = await this.stateGenerator.generateFromPythonClass(options.stateFile, options.stateClass);
          
          // Create shared types directory
          const sharedTypesDir = 'src/types/generated';
          await fs.mkdir(sharedTypesDir, { recursive: true });
          
          // Use state class name for file naming, not device ID
          const stateInterfacePath = path.join(sharedTypesDir, `${options.stateClass}.state.ts`);
          const stateHookPath = path.join(this.outputDir, `${deviceId}.hooks.ts`);
          
          // Check if state interface already exists
          let stateAlreadyExists = false;
          try {
            await fs.access(stateInterfacePath);
            stateAlreadyExists = true;
            console.log(`♻️  State interface already exists: ${stateInterfacePath}`);
          } catch {
            // File doesn't exist, we need to generate it
          }
          
          // Generate state interface only if it doesn't exist
          if (!stateAlreadyExists) {
            customStateInterface = this.stateGenerator.generateStateInterface(stateDefinition);
            await fs.writeFile(stateInterfacePath, customStateInterface, 'utf8');
            console.log(`✅ Generated shared state interface: ${stateInterfacePath}`);
          }
          
          // Always generate device-specific hook (but update imports to shared state)
          const stateHook = await this.stateGenerator.generateStateHook(stateDefinition, deviceId, options.stateClass);
          await fs.writeFile(stateHookPath, stateHook, 'utf8');
          console.log(`✅ Generated device hook: ${stateHookPath}`);
          
        } catch (error) {
          console.warn(`⚠️  Failed to generate Python state types: ${error.message}`);
          console.warn('   Continuing with default state generation...');
        }
      }
      
      // Generate component
      const template = new DevicePageTemplate();
      const componentCode = template.generateComponent(structure);
      
      // Ensure output directory exists
      await fs.mkdir(this.outputDir, { recursive: true });
      
      // Write file
      const outputPath = path.join(this.outputDir, `${deviceId}.gen.tsx`);
      await fs.writeFile(outputPath, componentCode, 'utf8');
      
      const duration = Date.now() - startTime;
      console.log(`✅ Generated: ${outputPath} (${duration}ms)`);
      
      return { 
        success: true, 
        outputPath,
        deviceClass: validatedConfig.device_class,
        sectionsGenerated: structure.uiSections.length,
        duration,
        deviceId
      };
      
    } catch (error) {
      const duration = Date.now() - startTime;
      const errorMessage = error instanceof Error ? error.message : String(error);
      console.error(`❌ Generation failed for ${deviceId} (${duration}ms):`, errorMessage);
      
      // Add more specific error context
      if (errorMessage.includes('fetch')) {
        console.error('💡 Tip: Make sure the backend API is running and accessible');
      } else if (errorMessage.includes('Unsupported device class')) {
        console.error('💡 Tip: This device class is not yet supported in Phase 1');
      }
      
      return { 
        success: false, 
        error: errorMessage,
        duration,
        deviceId 
      };
    }
  }
  
  async listSupportedDeviceClasses(): Promise<string[]> {
    return Array.from(this.handlers.keys());
  }
  
  async testApiConnection(): Promise<boolean> {
    try {
      const isAvailable = await this.client.validateConnectivity();
      if (isAvailable) {
        console.log('✅ API connection successful');
        return true;
      } else {
        console.log('❌ API connection failed');
        return false;
      }
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : String(error);
      console.error('❌ API connection error:', errorMessage);
      return false;
    }
  }
  
  getApiBaseUrl(): string {
    return this.apiBaseUrl;
  }

  // Phase 3 Methods
  async validateGeneratedCode(deviceId?: string): Promise<any> {
    console.log('🔍 Validating generated code...');
    
    if (deviceId) {
      const filePath = path.join(this.outputDir, `${deviceId}.gen.tsx`);
      const compilationResult = await this.codeValidator.validateTypeScriptCompilation(filePath);
      const importResult = await this.codeValidator.validateImportResolution(filePath);
      
      return {
        deviceId,
        compilation: compilationResult,
        imports: importResult,
        success: compilationResult.success && importResult.allImportsResolved
      };
    } else {
      return await this.codeValidator.validateAllGeneratedFiles(this.outputDir);
    }
  }

  async validateGeneratedComponents(deviceId?: string): Promise<any> {
    console.log('🧪 Validating generated components...');
    
    if (deviceId) {
      const filePath = path.join(this.outputDir, `${deviceId}.gen.tsx`);
      return await this.componentValidator.validateComponentRendering(filePath);
    } else {
      return await this.componentValidator.validateAllGeneratedComponents(this.outputDir);
    }
  }

  async generateStateTypes(config: any): Promise<string> {
    console.log('📝 Generating state types...');
    const stateDefinition = await this.stateGenerator.generateFromDeviceConfig(config);
    return this.stateGenerator.generateStateInterface(stateDefinition);
  }

  async generateRouterManifest(deviceStructures: any[]): Promise<void> {
    console.log('🗺️ Generating router manifest...');
    
    const deviceEntries = deviceStructures.map(structure => 
      this.routerIntegration.createDevicePageEntry(structure, path.join(this.outputDir, `${structure.deviceId}.gen.tsx`))
    );

    const manifest = await this.routerIntegration.generateRouterManifest(deviceEntries);
    const registry = await this.routerIntegration.generateDeviceRegistry(deviceEntries);
    const navigation = await this.routerIntegration.generateNavigationConfig(deviceEntries);

    // Write router files
    await fs.writeFile(manifest.filepath, manifest.content, 'utf8');
    await fs.writeFile(registry.filepath, registry.content, 'utf8');
    await fs.writeFile(navigation.filepath, navigation.content, 'utf8');

    console.log(`✅ Generated router manifest: ${manifest.filepath}`);
    console.log(`✅ Generated device registry: ${registry.filepath}`);
    console.log(`✅ Generated navigation config: ${navigation.filepath}`);
  }

  async generateDocumentation(deviceStructures: any[]): Promise<void> {
    console.log('📚 Generating documentation...');
    
    // Ensure docs directory exists
    await fs.mkdir('docs/devices', { recursive: true });
    
    // Generate individual device documentation
    for (const structure of deviceStructures) {
      const deviceDoc = await this.docGenerator.generateDeviceDocumentation(structure);
      await fs.writeFile(deviceDoc.filepath, deviceDoc.content, 'utf8');
      console.log(`📄 Generated docs: ${deviceDoc.filepath}`);
    }

    // Generate system documentation
    const systemDoc = await this.docGenerator.generateSystemDocumentation(deviceStructures);
    await fs.writeFile(systemDoc.filepath, systemDoc.content, 'utf8');
    console.log(`📄 Generated system docs: ${systemDoc.filepath}`);
  }

  async runFullValidationSuite(): Promise<any> {
    console.log('🔬 Running full validation suite...');
    
    const results = {
      codeValidation: await this.validateGeneratedCode(),
      componentValidation: await this.validateGeneratedComponents(),
      timestamp: new Date().toISOString()
    };

    console.log('\n📊 Validation Results:');
    console.log(`Code Validation: ${results.codeValidation.overallSuccess ? '✅ PASS' : '❌ FAIL'}`);
    console.log(`Component Validation: ${results.componentValidation.overallSuccess ? '✅ PASS' : '❌ FAIL'}`);
    
    if (!results.codeValidation.overallSuccess) {
      console.log('\n❌ Code Validation Issues:');
      results.codeValidation.compilationResults.forEach((result: any) => {
        if (!result.success) {
          console.log(`  ${result.filePath}: ${result.errors.length} errors`);
        }
      });
    }

    if (!results.componentValidation.overallSuccess) {
      console.log('\n❌ Component Validation Issues:');
      results.componentValidation.results.forEach((result: any) => {
        if (!result.rendersWithoutCrash) {
          console.log(`  ${result.filePath}: ${result.renderErrors.length} errors`);
        }
      });
    }

    return results;
  }

  async generateCompleteSystem(deviceStructures: any[]): Promise<void> {
    console.log('🏗️ Generating complete system...');
    
    // Generate router integration
    await this.generateRouterManifest(deviceStructures);
    
    // Generate documentation
    await this.generateDocumentation(deviceStructures);
    
    // Run validation suite
    await this.runFullValidationSuite();
    
    console.log('✅ Complete system generation finished!');
  }
}

// CLI Interface function
async function runCLI() {
  const args = process.argv.slice(2);
  
  // Parse command line arguments
  const deviceId = args.find(arg => arg.startsWith('--device-id='))?.split('=')[1];
  const deviceIds = args.find(arg => arg.startsWith('--device-ids='))?.split('=')[1]?.split(',');
  const deviceClasses = args.find(arg => arg.startsWith('--device-classes='))?.split('=')[1]?.split(',');
  const apiBaseUrl = args.find(arg => arg.startsWith('--api-base-url='))?.split('=')[1] || 'http://192.168.110.250:8000';
  const outputDir = args.find(arg => arg.startsWith('--output-dir='))?.split('=')[1] || 'src/pages/devices';
  const testConnection = args.includes('--test-connection');
  const listClasses = args.includes('--list-classes');
  const showHelp = args.includes('--help') || args.includes('-h');
  const batchMode = args.includes('--batch');
  const maxConcurrency = parseInt(args.find(arg => arg.startsWith('--max-concurrency='))?.split('=')[1] || '3');
  
  // Python state generation options
  const stateFile = args.find(arg => arg.startsWith('--state-file='))?.split('=')[1];
  const stateClass = args.find(arg => arg.startsWith('--state-class='))?.split('=')[1];
  
  // Phase 3 options
  const validateCode = args.includes('--validate-code');
  const validateComponents = args.includes('--validate-components');
  const generateDocs = args.includes('--generate-docs');
  const generateRouter = args.includes('--generate-router');
  const runValidation = args.includes('--run-validation');
  const fullSystem = args.includes('--full-system');
  
  if (showHelp) {
    console.log(`
🚀 Device Page Generator - Phase 3 (Production Ready)

Usage:
  npm run gen:device-pages -- [options]

Single Device Options:
  --device-id=<id>        Device ID to generate page for
  --state-file=<path>     Python file containing device state class (optional)
  --state-class=<name>    Python class name for state generation (optional)

Batch Processing Options:
  --batch                 Process all available devices
  --device-ids=<ids>      Comma-separated list of device IDs to process
  --device-classes=<cls>  Comma-separated list of device classes to process
  --max-concurrency=<n>   Max concurrent generations (default: 3)

Phase 3 Validation & Integration Options:
  --validate-code         Validate TypeScript compilation of generated files
  --validate-components   Validate React component structure
  --generate-docs         Generate comprehensive documentation
  --generate-router       Generate router integration files
  --run-validation        Run complete validation suite
  --full-system           Generate complete system with all Phase 3 features

General Options:
  --api-base-url=<url>    API base URL (default: http://192.168.110.250:8000)
  --output-dir=<path>     Output directory (default: src/pages/devices)
  --test-connection       Test API connection only
  --list-classes         List supported device classes
  --help, -h             Show this help message

Examples:
  # Generate page for a specific device
  npm run gen:device-pages -- --device-id=living_room_tv

  # Generate page with custom Python state class
  npm run gen:device-pages -- --device-id=living_room_tv \\
    --state-file=backend/devices/lg_tv_state.py --state-class=LgTvState

  # Process multiple specific devices
  npm run gen:device-pages -- --device-ids=tv1,tv2,soundbar1

  # Process all LG TVs and Apple TVs with full system generation
  npm run gen:device-pages -- --device-classes=LgTv,AppleTVDevice --full-system

  # Validate all generated code
  npm run gen:device-pages -- --validate-code --validate-components

  # Generate complete system with docs and router integration
  npm run gen:device-pages -- --batch --full-system
  npm run gen:device-pages -- --batch --device-classes=LgTv,AppleTVDevice

  # Process all available devices
  npm run gen:device-pages -- --batch

  # Test API connection
  npm run gen:device-pages -- --test-connection

Supported Device Classes (Phase 2):
  - WirenboardIRDevice (IR Remote Control)
  - LgTv (Smart TV with Pointer Control)
  - EMotivaXMC2 (Audio Processor with Multi-Zone)
  - BroadlinkKitchenHood (Kitchen Hood with Parameters)
  - AppleTVDevice (Apple TV Remote Control)
    `);
    process.exit(0);
  }
  
  const generator = new DevicePageGenerator(apiBaseUrl, outputDir);
  
  try {
    if (testConnection) {
      console.log(`🔗 Testing connection to ${apiBaseUrl}...`);
      const success = await generator.testApiConnection();
      process.exit(success ? 0 : 1);
    }
    
    if (listClasses) {
      console.log('📋 Supported device classes:');
      const classes = await generator.listSupportedDeviceClasses();
      classes.forEach(cls => console.log(`  - ${cls}`));
      process.exit(0);
    }

    // Phase 3 commands
    if (validateCode) {
      console.log('🔍 Running code validation...');
      const results = await generator.validateGeneratedCode();
      console.log(results.overallSuccess ? '✅ Code validation passed' : '❌ Code validation failed');
      process.exit(results.overallSuccess ? 0 : 1);
    }

    if (validateComponents) {
      console.log('🧪 Running component validation...');
      const results = await generator.validateGeneratedComponents();
      console.log(results.overallSuccess ? '✅ Component validation passed' : '❌ Component validation failed');
      process.exit(results.overallSuccess ? 0 : 1);
    }

    if (runValidation) {
      console.log('🔬 Running complete validation suite...');
      const results = await generator.runFullValidationSuite();
      const allPassed = results.codeValidation.overallSuccess && results.componentValidation.overallSuccess;
      process.exit(allPassed ? 0 : 1);
    }
    
    // Handle batch processing (but not single device with just generateRouter)
    if (batchMode || deviceIds || deviceClasses || fullSystem || generateDocs || (generateRouter && !deviceId)) {
      console.log(`🎯 Device Page Generator - Phase 3 ${fullSystem ? '(Full System)' : '(Batch Mode)'}`);
      console.log(`📡 API: ${apiBaseUrl}`);
      console.log(`📁 Output: ${outputDir}`);
      console.log(`⚡ Max Concurrency: ${maxConcurrency}`);
      console.log('');
      
      const batchProcessor = new BatchProcessor(generator);
      let result;
      let deviceStructures: any[] = [];
      
      if (deviceIds) {
        console.log(`🎯 Processing specific devices: [${deviceIds.join(', ')}]`);
        result = await batchProcessor.processDeviceList(deviceIds, { maxConcurrency });
      } else {
        result = await batchProcessor.processAllDevices({ 
          deviceClasses, 
          maxConcurrency 
        });
      }

      // For Phase 3 features, we need to collect device structures
      if (fullSystem || generateDocs || generateRouter) {
        console.log('\n🔄 Collecting device structures for Phase 3 processing...');
        // We'd need to modify BatchProcessor to return device structures
        // For now, we'll generate from successful device IDs
        const successfulDeviceIds = result.details
          .filter((detail: any) => detail.success)
          .map((detail: any) => detail.deviceId);

        for (const deviceId of successfulDeviceIds) {
          try {
            // Re-fetch to get structure - not ideal but works for Phase 3
            const [config, groups] = await Promise.all([
              generator['client'].fetchDeviceConfig(deviceId),
              generator['client'].fetchDeviceGroups(deviceId)
            ]);
            
            const validatedConfig = generator['validator'].validateDeviceConfig(config);
            const handler = generator['handlers'].get(validatedConfig.device_class);
            
            if (handler) {
              const structure = handler.analyzeStructure(validatedConfig, groups);
              deviceStructures.push(structure);
            }
          } catch (error) {
            console.warn(`⚠️  Could not collect structure for ${deviceId}: ${error.message}`);
          }
        }

        console.log(`📊 Collected ${deviceStructures.length} device structures`);
      }

      // Phase 3 features
      if (generateRouter || fullSystem) {
        if (deviceStructures.length > 0) {
          await generator.generateRouterManifest(deviceStructures);
        } else {
          console.warn('⚠️  No device structures available for router generation');
        }
      }

      if (generateDocs || fullSystem) {
        if (deviceStructures.length > 0) {
          await generator.generateDocumentation(deviceStructures);
        } else {
          console.warn('⚠️  No device structures available for documentation generation');
        }
      }

      if (fullSystem) {
        console.log('\n🏗️ Running full system generation...');
        if (deviceStructures.length > 0) {
          await generator.generateCompleteSystem(deviceStructures);
        } else {
          console.warn('⚠️  No device structures available for full system generation');
        }
      }
      
      process.exit(result.successRate > 0 ? 0 : 1);
    }
    
    // Single device processing
    if (!deviceId) {
      console.error('❌ --device-id is required for single device generation');
      console.error('Use --batch for batch processing or --help for usage information');
      process.exit(1);
    }
    
    // Validate Python state options
    if ((stateFile && !stateClass) || (!stateFile && stateClass)) {
      console.error('❌ Both --state-file and --state-class must be provided together');
      console.error('Use --help for usage information');
      process.exit(1);
    }
    
    console.log('🎯 Device Page Generator - Phase 2');
    console.log(`📡 API: ${apiBaseUrl}`);
    console.log(`📁 Output: ${outputDir}`);
    console.log(`🔧 Device: ${deviceId}`);
    if (stateFile && stateClass) {
      console.log(`🐍 Python State: ${stateFile}::${stateClass}`);
    }
    console.log('');
    
    const result = await generator.generateDevicePage(deviceId, { stateFile, stateClass });
    
    // Handle router generation for single device
    if (result.success && generateRouter) {
      console.log('\n🗺️ Generating router integration for single device...');
      try {
        // Collect device structure for router generation
        const [config, groups] = await Promise.all([
          generator['client'].fetchDeviceConfig(deviceId),
          generator['client'].fetchDeviceGroups(deviceId)
        ]);
        
        const validatedConfig = generator['validator'].validateDeviceConfig(config);
        const handler = generator['handlers'].get(validatedConfig.device_class);
        
        if (handler) {
          const structure = handler.analyzeStructure(validatedConfig, groups);
          const deviceEntry = generator['routerIntegration'].createDevicePageEntry(structure, result.outputPath!);
          
          // Use incremental router generation to merge with existing entries
          await generator['routerIntegration'].generateIncrementalRouterFiles(deviceEntry);
          console.log('✅ Router generation completed');
        } else {
          console.warn(`⚠️  No handler found for device class: ${validatedConfig.device_class}`);
        }
      } catch (error) {
        console.error('❌ Router generation failed:', error.message);
      }
    }
    
    if (result.success) {
      console.log('');
      console.log('🎉 Generation completed successfully!');
      console.log(`📄 File: ${result.outputPath}`);
      console.log(`⚡ Device Class: ${result.deviceClass}`);
      console.log(`📊 UI Sections: ${result.sectionsGenerated}`);
      console.log(`⏱️  Duration: ${result.duration}ms`);
    }
    
    process.exit(result.success ? 0 : 1);
    
  } catch (error) {
    const errorMessage = error instanceof Error ? error.message : String(error);
    console.error('💥 Unexpected error:', errorMessage);
    if (error instanceof Error && error.stack) {
      console.error('🔍 Stack trace:', error.stack);
    }
    process.exit(1);
  }
}

// Run CLI if this file is executed directly
// Note: In Node.js with tsx, the file check is handled differently
runCLI(); 