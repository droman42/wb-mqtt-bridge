import { spawn } from 'child_process';
import process from 'node:process';
import * as _fs from 'fs/promises';
import * as _path from 'path';
import { DeviceConfig, CommandParameter } from '../types/DeviceConfig';

export interface StateDefinition {
  interfaceName: string;
  fields: StateField[];
  imports: string[];
  extends: string[];
}

export interface StateField {
  name: string;
  type: string;
  optional: boolean;
  description: string;
  defaultValue?: any;
}

export interface PythonParsingResult {
  success: boolean;
  fields: any[];
  error?: string;
}

export class StateTypeGenerator {
  private importCache = new Map<string, StateDefinition>();
  private readonly CACHE_TTL = 5 * 60 * 1000; // 5 minutes
  
  /**
   * Generate TypeScript state definition from Python class using package import path
   * @param importPath - Package import path in format "module.path:ClassName"
   * @returns Promise<StateDefinition>
   */
  async generateFromImportPath(importPath: string): Promise<StateDefinition> {
    // Check cache first
    const cached = this.importCache.get(importPath);
    if (cached) {
      console.log(`⚡ Using cached types for: ${importPath}`);
      return cached;
    }
    
    try {
      console.log(`🐍 Generating types from package import: ${importPath}`);
      
      // Parse import path (e.g., "wb_mqtt_bridge.domain.devices.models:WirenboardIRState")
      const [modulePath, className] = importPath.split(':');
      
      if (!modulePath || !className) {
        throw new Error(`Invalid import path format: ${importPath}. Expected format: "module.path:ClassName"`);
      }

      // Try to parse Python class using importlib
      const pythonResult = await this.parsePythonClassFromImport(modulePath, className);
      
      if (pythonResult.success) {
        console.log(`✅ Successfully parsed ${className} from ${modulePath}`);
        const stateDefinition = this.convertToStateDefinition(className, pythonResult.fields);
        // Cache the result
        this.importCache.set(importPath, stateDefinition);
        return stateDefinition;
      } else {
        console.warn(`Python parsing failed for ${importPath}: ${pythonResult.error}`);
        // Fallback to basic state generation
        const basicDefinition = this.generateBasicStateDefinition(className);
        this.importCache.set(importPath, basicDefinition);
        return basicDefinition;
      }
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : String(error);
      console.warn(`Import-based state generation failed for ${importPath}: ${errorMessage}`);
      // Extract class name from import path for fallback
      const className = importPath.split(':')[1] || 'UnknownState';
      const fallbackDefinition = this.generateBasicStateDefinition(className);
      this.importCache.set(importPath, fallbackDefinition);
      return fallbackDefinition;
    }
  }



  /**
   * Generate TypeScript state definition from Python class using package import path
   * @param options - Generation options with importPath
   * @returns Promise<StateDefinition>
   */
  async generateFromPythonState(options: {
    importPath: string;
  }): Promise<StateDefinition> {
    return this.generateFromImportPath(options.importPath);
  }

  /**
   * Phase 2: Generate TypeScript state definition for scenario virtual devices
   * @param scenarioId - Scenario ID to generate virtual device state for
   * @returns Promise<StateDefinition>
   */
  async generateFromScenarioWBConfig(scenarioId: string): Promise<StateDefinition> {
    try {
      console.log(`🎮 Generating virtual device state for scenario: ${scenarioId}`);
      
      // For now, we'll generate a basic virtual device state structure
      // In the future, this could fetch from the actual ScenarioWBConfig API
      return this.generateScenarioVirtualDeviceState(scenarioId);
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : String(error);
      console.warn(`Scenario virtual device state generation failed for ${scenarioId}: ${errorMessage}`);
      return this.generateBasicVirtualDeviceState(scenarioId);
    }
  }

  async generateFromDeviceConfig(config: DeviceConfig): Promise<StateDefinition> {
    const className = `${config.device_class}State`;
    
    // Extract parameters from all commands to build state interface
    const allParameters = new Map<string, CommandParameter>();
    
    Object.values(config.commands).forEach(command => {
      if (command.params) {
        command.params.forEach(param => {
          if (!allParameters.has(param.name)) {
            allParameters.set(param.name, param);
          }
        });
      }
    });

    const fields: StateField[] = Array.from(allParameters.values()).map(param => ({
      name: param.name,
      type: this.mapParameterTypeToTypeScript(param),
      optional: !param.required,
      description: param.description || `State for ${param.name}`,
      defaultValue: param.default
    }));

    // Note: Common device state fields (isConnected, lastUpdated, deviceId, deviceName, lastCommand, error) 
    // are inherited from BaseDeviceState - no need to add them explicitly

    return {
      interfaceName: className,
      fields,
      imports: ['BaseDeviceState'],
      extends: ['BaseDeviceState']
    };
  }

  generateStateInterface(stateDefinition: StateDefinition): string {
    const { interfaceName, fields, imports, extends: extendsClause } = stateDefinition;

    const importStatements = imports.length > 0 
      ? `import { ${imports.join(', ')} } from '../BaseDeviceState';\n\n`
      : '';

    const extendsStatement = extendsClause.length > 0 
      ? ` extends ${extendsClause.join(', ')}`
      : '';

    const fieldsCode = fields.map(field => 
      `  ${field.name}${field.optional ? '?' : ''}: ${field.type}; // ${field.description}`
    ).join('\n');

    // Generate default object with base fields + device-specific fields
    const baseDefaults = [
      '  device_id: ""',
      '  device_name: ""',
      '  last_command: null',
      '  error: null'
    ];
    
    const deviceSpecificDefaults = fields.map(field => 
      `  ${field.name}: ${this.formatDefaultValue(field)}`
    );
    
    const allDefaults = [...baseDefaults, ...deviceSpecificDefaults];

    return `${importStatements}export interface ${interfaceName}${extendsStatement} {
${fieldsCode}
}

export const default${interfaceName}: ${interfaceName} = {
${allDefaults.join(',\n')}
};`;
  }

  async generateStateHook(stateDefinition: StateDefinition, deviceId: string, stateClassName?: string): Promise<string> {
    const { interfaceName } = stateDefinition;
    const hookName = `use${interfaceName.replace('State', '')}`;
    
    // Determine import path based on whether we have a shared state class
    const importPath = stateClassName 
      ? `../../types/generated/${stateClassName}.state`
      : `../types/${interfaceName}`;

    return `import { useState, useEffect } from 'react';
import { ${interfaceName}, default${interfaceName} } from '${importPath}';
import { useDeviceState } from '../../hooks/useDeviceState';

export function ${hookName}(deviceId: string = '${deviceId}') {
  const [state, setState] = useState<${interfaceName}>(default${interfaceName});
  const { subscribeToState, updateState } = useDeviceState(deviceId);

  useEffect(() => {
    const subscription = subscribeToState((newState: Partial<${interfaceName}>) => {
      setState(prevState => ({ ...prevState, ...newState }));
    });

    return subscription.unsubscribe;
  }, [deviceId, subscribeToState]);

  const updateField = <K extends keyof ${interfaceName}>(
    field: K, 
    value: ${interfaceName}[K]
  ) => {
    setState(prevState => ({ ...prevState, [field]: value }));
    updateState({ [field]: value });
  };

  return {
    state,
    updateField,
    setState: (newState: Partial<${interfaceName}>) => {
      setState(prevState => ({ ...prevState, ...newState }));
      updateState(newState);
    }
  };
}`;
  }

  private async parsePythonClassFromImport(modulePath: string, className: string): Promise<PythonParsingResult> {
    return new Promise((resolve) => {
      const pythonScript = `
import importlib
import ast
import sys
import json
import inspect

def extract_class_fields_from_import(module_path, class_name):
    try:
        # Import the module using importlib
        module = importlib.import_module(module_path)
        
        # Get the class from the module
        cls = getattr(module, class_name)
        
        # Try to get source and parse with AST if possible
        try:
            import inspect
            source = inspect.getsource(cls)
            tree = ast.parse(source)
            
            fields = []
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef) and node.name == class_name:
                    for item in node.body:
                        if isinstance(item, ast.AnnAssign) and isinstance(item.target, ast.Name):
                            field_type = 'Any'
                            try:
                                field_type = ast.unparse(item.annotation)
                            except:
                                pass
                            
                            default_value = None
                            if item.value:
                                try:
                                    default_value = ast.literal_eval(item.value)
                                except:
                                    default_value = str(item.value)
                            
                            fields.append({
                                'name': item.target.id,
                                'type': field_type,
                                'optional': default_value is not None,
                                'default': default_value
                            })
            return fields
            
        except Exception as ast_error:
            # Fallback: try to extract fields from class annotations if available
            try:
                if hasattr(cls, '__annotations__'):
                    fields = []
                    for field_name, field_type in cls.__annotations__.items():
                        # Skip private fields
                        if not field_name.startswith('_'):
                            fields.append({
                                'name': field_name,
                                'type': str(field_type),
                                'optional': hasattr(cls, field_name) and getattr(cls, field_name) is not None,
                                'default': getattr(cls, field_name, None) if hasattr(cls, field_name) else None
                            })
                    return fields
                else:
                    return []
            except Exception as annotation_error:
                return {'error': f'AST parsing failed: {ast_error}, Annotation parsing failed: {annotation_error}'}
        
    except Exception as e:
        return {'error': str(e)}

result = extract_class_fields_from_import(sys.argv[1], sys.argv[2])
print(json.dumps(result))
      `;

      // Use environment-specified Python executable or default to python3
      const pythonExecutable = process.env.PYTHON_EXECUTABLE || 'python3';
      const pythonProcess = spawn(pythonExecutable, ['-c', pythonScript, modulePath, className]);
      let output = '';
      let errorOutput = '';

      pythonProcess.stdout.on('data', (data) => {
        output += data.toString();
      });

      pythonProcess.stderr.on('data', (data) => {
        errorOutput += data.toString();
      });

      pythonProcess.on('close', (code) => {
        if (code === 0 && output) {
          try {
            const result = JSON.parse(output);
            if (result.error) {
              resolve({ success: false, fields: [], error: result.error });
            } else {
              resolve({ success: true, fields: result, error: undefined });
            }
          } catch (parseError) {
            const errorMessage = parseError instanceof Error ? parseError.message : String(parseError);
            resolve({ success: false, fields: [], error: `JSON parse error: ${errorMessage}` });
          }
        } else {
          resolve({ 
            success: false, 
            fields: [], 
            error: `Python execution failed (code ${code}): ${errorOutput || 'Unknown error'}` 
          });
        }
      });

      // Set a timeout to prevent hanging - optimized for package imports
      setTimeout(() => {
        pythonProcess.kill();
        resolve({ success: false, fields: [], error: 'Python execution timeout' });
      }, 10000); // Reduced timeout since package imports are faster
    });
  }



  private convertToStateDefinition(className: string, fields: any[]): StateDefinition {
    return {
      interfaceName: `${className}State`,
      fields: fields.map(field => ({
        name: field.name,
        type: this.mapPythonTypeToTypeScript(field.type),
        optional: field.optional,
        description: `State field for ${field.name}`,
        defaultValue: field.default
      })),
      imports: ['BaseDeviceState'],
      extends: ['BaseDeviceState']
    };
  }

  private generateBasicStateDefinition(className: string): StateDefinition {
    return {
      interfaceName: `${className}State`,
      fields: [
        // Only device-specific fields - base fields inherited from BaseDeviceState
        {
          name: 'deviceStatus',
          type: 'string',
          optional: false,
          description: 'Current device status',
          defaultValue: 'unknown'
        }
      ],
      imports: ['BaseDeviceState'],
      extends: ['BaseDeviceState']
    };
  }

  private mapPythonTypeToTypeScript(pythonType: string): string {
    const typeMap: Record<string, string> = {
      'str': 'string',
      'int': 'number',
      'float': 'number',
      'bool': 'boolean',
      'list': 'any[]',
      'dict': 'Record<string, any>',
      'Any': 'any',
      'Optional[str]': 'string | null',
      'Optional[int]': 'number | null',
      'Optional[float]': 'number | null',
      'Optional[bool]': 'boolean | null',
      'List[str]': 'string[]',
      'List[int]': 'number[]',
      'Dict[str, Any]': 'Record<string, any>'
    };

    return typeMap[pythonType] || 'any';
  }

  private mapParameterTypeToTypeScript(param: CommandParameter): string {
    switch (param.type) {
      case 'range':
        return 'number';
      case 'integer':
        return 'number';
      case 'string':
        return 'string';
      default:
        return 'any';
    }
  }

  private formatDefaultValue(field: StateField): string {
    if (field.defaultValue === null) {
      // Only return null if the type is actually nullable
      if (field.type.includes('null')) {
        return 'null';
      }
      // For non-nullable types, provide appropriate defaults
      switch (field.type) {
        case 'boolean':
          return 'false';
        case 'number':
          return '0';
        case 'string':
          return "''";
        default:
          return 'null';
      }
    }
    if (field.defaultValue === undefined) {
      switch (field.type) {
        case 'boolean':
          return 'false';
        case 'number':
          return '0';
        case 'string':
          return "''";
        case 'Date | null':
          return 'null';
        default:
          if (field.type.includes('null')) {
            return 'null';
          }
          return 'null';
      }
    }
    if (typeof field.defaultValue === 'string') {
      return `'${field.defaultValue}'`;
    }
    return String(field.defaultValue);
  }

  /**
   * Phase 2: Generate state definition for scenario virtual devices
   * @param scenarioId - Scenario ID
   * @returns StateDefinition
   */
  private generateScenarioVirtualDeviceState(scenarioId: string): StateDefinition {
    const interfaceName = `${this.formatScenarioClassName(scenarioId)}VirtualState`;
    
    // Common virtual device state fields based on WB device patterns
    const fields: StateField[] = [
      {
        name: 'scenario_id',
        type: 'string',
        optional: false,
        description: 'Scenario identifier',
        defaultValue: scenarioId
      },
      {
        name: 'scenario_active',
        type: 'boolean',
        optional: false,
        description: 'Whether the scenario is currently active',
        defaultValue: false
      },
      {
        name: 'virtual_controls',
        type: 'Record<string, any>',
        optional: true,
        description: 'Virtual control states for WB integration',
        defaultValue: {}
      },
      {
        name: 'last_command_result',
        type: 'string | null',
        optional: true,
        description: 'Result of the last executed command',
        defaultValue: null
      },
      {
        name: 'startup_sequence_complete',
        type: 'boolean',
        optional: true,
        description: 'Whether the startup sequence has completed',
        defaultValue: false
      },
      {
        name: 'shutdown_sequence_complete',
        type: 'boolean',
        optional: true,
        description: 'Whether the shutdown sequence has completed',
        defaultValue: true
      }
    ];

    return {
      interfaceName,
      fields,
      imports: ['BaseDeviceState'],
      extends: ['BaseDeviceState']
    };
  }

  /**
   * Generate basic virtual device state as fallback
   * @param scenarioId - Scenario ID
   * @returns StateDefinition
   */
  private generateBasicVirtualDeviceState(scenarioId: string): StateDefinition {
    const interfaceName = `${this.formatScenarioClassName(scenarioId)}VirtualState`;
    
    return {
      interfaceName,
      fields: [
        {
          name: 'scenario_id',
          type: 'string',
          optional: false,
          description: 'Scenario identifier',
          defaultValue: scenarioId
        },
        {
          name: 'status',
          type: 'string',
          optional: false,
          description: 'Virtual device status',
          defaultValue: 'unknown'
        }
      ],
      imports: ['BaseDeviceState'],
      extends: ['BaseDeviceState']
    };
  }

  /**
   * Format scenario ID to valid TypeScript class name
   * @param scenarioId - Scenario ID to format
   * @returns Formatted class name
   */
  private formatScenarioClassName(scenarioId: string): string {
    return scenarioId
      .split(/[-_]/)
      .map(part => part.charAt(0).toUpperCase() + part.slice(1).toLowerCase())
      .join('');
  }
} 