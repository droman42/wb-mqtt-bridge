import { spawn } from 'child_process';
import * as fs from 'fs/promises';
import * as path from 'path';
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
  async generateFromPythonClass(filePath: string, className: string): Promise<StateDefinition> {
    try {
      // Try to parse Python class first
      const pythonResult = await this.parsePythonClass(filePath, className);
      
      if (pythonResult.success) {
        return this.convertToStateDefinition(className, pythonResult.fields);
      } else {
        // Fallback to basic state generation
        console.warn(`Python parsing failed for ${className}: ${pythonResult.error}`);
        return this.generateBasicStateDefinition(className);
      }
    } catch (error) {
      console.warn(`State generation failed for ${className}: ${error.message}`);
      return this.generateBasicStateDefinition(className);
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
      '  deviceId: ""',
      '  deviceName: ""',
      '  lastCommand: null',
      '  error: null',
      '  isConnected: false',
      '  lastUpdated: null'
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

  private async parsePythonClass(filePath: string, className: string): Promise<PythonParsingResult> {
    return new Promise((resolve) => {
      const pythonScript = `
import ast
import sys
import json

def extract_class_fields(file_path, class_name):
    try:
        with open(file_path, 'r') as f:
            tree = ast.parse(f.read())
        
        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and node.name == class_name:
                fields = []
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
        return []
    except Exception as e:
        return {'error': str(e)}

result = extract_class_fields(sys.argv[1], sys.argv[2])
print(json.dumps(result))
      `;

      const process = spawn('python3', ['-c', pythonScript, filePath, className]);
      let output = '';
      let errorOutput = '';

      process.stdout.on('data', (data) => {
        output += data.toString();
      });

      process.stderr.on('data', (data) => {
        errorOutput += data.toString();
      });

      process.on('close', (code) => {
        if (code === 0 && output) {
          try {
            const result = JSON.parse(output);
            if (result.error) {
              resolve({ success: false, fields: [], error: result.error });
            } else {
              resolve({ success: true, fields: result, error: undefined });
            }
          } catch (parseError) {
            resolve({ success: false, fields: [], error: `JSON parse error: ${parseError.message}` });
          }
        } else {
          resolve({ 
            success: false, 
            fields: [], 
            error: `Python execution failed (code ${code}): ${errorOutput || 'Unknown error'}` 
          });
        }
      });

      // Set a timeout to prevent hanging
      setTimeout(() => {
        process.kill();
        resolve({ success: false, fields: [], error: 'Python execution timeout' });
      }, 10000);
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
      return 'null';
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
          return 'null';
      }
    }
    if (typeof field.defaultValue === 'string') {
      return `'${field.defaultValue}'`;
    }
    return String(field.defaultValue);
  }
} 