/* global process */
import { readFileSync, existsSync } from 'fs';
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

// Fields contributed by the TypeScript BaseDeviceState interface (src/BaseDeviceState.ts).
// They are inherited via `extends BaseDeviceState`, so they must be excluded from each
// device-specific interface to avoid redeclaration. Note `power` is intentionally NOT
// here: it lives on the backend BaseDeviceState but not the TS one, so it flows through
// as a device-specific field (matching the previous generator's output).
const TS_BASE_STATE_FIELDS = new Set(['device_id', 'device_name', 'last_command', 'error']);

export class StateTypeGenerator {
  private importCache = new Map<string, StateDefinition>();
  private openApiCache: any | null = null;
  private readonly CACHE_TTL = 5 * 60 * 1000; // 5 minutes

  /**
   * Generate a TypeScript state definition for a backend state model by reading its
   * JSON Schema from the committed OpenAPI snapshot (wb-mqtt-bridge/openapi.json).
   *
   * This replaces the previous approach of spawning python3 to importlib-import the
   * package and AST-parse the Pydantic class — which forced Python + `pip install -e
   * ./wb-mqtt-bridge` into the UI build and broke silently on a backend rename
   * (action_plan P1 #3.5). The OpenAPI contract is now the single source of truth.
   *
   * @param importPath - Legacy import path in format "module.path:ClassName"; only the
   *   ClassName segment is used now (the module path is ignored).
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
      // Accept both "module.path:ClassName" and bare "ClassName".
      const className = importPath.includes(':') ? importPath.split(':')[1] : importPath;

      if (!className) {
        throw new Error(`Invalid import path format: ${importPath}. Expected "module.path:ClassName" or "ClassName"`);
      }

      console.log(`📗 Generating types for ${className} from OpenAPI schema`);
      const fields = this.extractFieldsFromOpenApi(className);

      if (fields) {
        console.log(`✅ Resolved ${className} from OpenAPI (${fields.length} device-specific fields)`);
        const stateDefinition: StateDefinition = {
          interfaceName: `${className}State`,
          fields,
          imports: ['BaseDeviceState'],
          extends: ['BaseDeviceState'],
        };
        this.importCache.set(importPath, stateDefinition);
        return stateDefinition;
      }

      console.warn(`${className} not found as a device-state model in OpenAPI; using basic definition`);
      const basicDefinition = this.generateBasicStateDefinition(className);
      this.importCache.set(importPath, basicDefinition);
      return basicDefinition;
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : String(error);
      console.warn(`OpenAPI-based state generation failed for ${importPath}: ${errorMessage}`);
      // Extract class name from import path for fallback
      const className = (importPath.includes(':') ? importPath.split(':')[1] : importPath) || 'UnknownState';
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

  async generateStateHook(stateDefinition: StateDefinition, deviceId: string, stateClassName?: string, deviceClass?: string): Promise<string> {
    const { interfaceName } = stateDefinition;
    const hookName = `use${interfaceName.replace('State', '')}`;
    const isScenario = deviceClass === 'ScenarioDevice';
    
    // Determine import path based on whether we have a shared state class
    const importPath = stateClassName 
      ? `../../types/generated/${stateClassName}.state`
      : `../types/${interfaceName}`;

    // Use appropriate state hook based on device type
    const stateHookImport = isScenario ? 'useScenarioState' : 'useDeviceState';
    const stateHookPath = isScenario ? '../../hooks/useScenarioState' : '../../hooks/useDeviceState';
    
    if (isScenario) {
      // Generate scenario-specific hook
      return `import { useState, useEffect } from 'react';
import { ${interfaceName}, default${interfaceName} } from '${importPath}';
import { ${stateHookImport} } from '${stateHookPath}';

export function ${hookName}(scenarioId: string = '${deviceId}') {
  const [state, setState] = useState<${interfaceName}>(default${interfaceName});
  const { state: scenarioState, isLoading, error } = ${stateHookImport}(scenarioId);

  // Update local state when scenario state changes
  useEffect(() => {
    if (scenarioState && scenarioState.devices) {
      // Map scenario devices to local config state if needed
      // For now, we'll just keep the default state structure
      setState(prevState => ({ ...prevState }));
    }
  }, [scenarioState]);

  const updateField = <K extends keyof ${interfaceName}>(
    field: K, 
    value: ${interfaceName}[K]
  ) => {
    setState(prevState => ({ ...prevState, [field]: value }));
    // Note: For scenarios, we may need different update logic
    // This depends on how scenario config updates are handled
  };

  return {
    state,
    updateField,
    setState: (newState: Partial<${interfaceName}>) => {
      setState(prevState => ({ ...prevState, ...newState }));
    },
    scenarioState,
    isLoading,
    error
  };
}`;
    } else {
      // Generate device-specific hook
      return `import { useState, useEffect } from 'react';
import { ${interfaceName}, default${interfaceName} } from '${importPath}';
import { ${stateHookImport} } from '${stateHookPath}';

export function ${hookName}(deviceId: string = '${deviceId}') {
  const [state, setState] = useState<${interfaceName}>(default${interfaceName});
  const { subscribeToState, updateState } = ${stateHookImport}(deviceId);

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
  }

  /**
   * Load and cache the backend OpenAPI snapshot. Resolves the path from the
   * WB_OPENAPI_SCHEMA env var, then well-known monorepo locations
   * (Docker/CI layout `backend/openapi.json` with the backend copied alongside the UI build,
   * local dev `../backend/openapi.json` when run from `ui/`). Returns null if none is found.
   */
  private loadOpenApiSchema(): any | null {
    if (this.openApiCache) return this.openApiCache;

    const candidates = [
      process.env.WB_OPENAPI_SCHEMA,
      'backend/openapi.json',
      '../backend/openapi.json',
      'openapi.json',
    ].filter(Boolean) as string[];

    for (const candidate of candidates) {
      try {
        if (existsSync(candidate)) {
          this.openApiCache = JSON.parse(readFileSync(candidate, 'utf8'));
          console.log(`📗 Loaded OpenAPI schema from: ${candidate}`);
          return this.openApiCache;
        }
      } catch (error) {
        const message = error instanceof Error ? error.message : String(error);
        console.warn(`Failed to read OpenAPI schema at ${candidate}: ${message}`);
      }
    }

    console.warn('⚠️  OpenAPI schema not found (set WB_OPENAPI_SCHEMA or check the sibling checkout)');
    return null;
  }

  /**
   * Extract device-specific state fields for a model from the OpenAPI schema.
   * Returns null when the schema is unavailable or the model is not a device-state
   * model (heuristic: a device-state schema carries the base `last_command` and
   * `error` fields — config models like ScenarioWBConfig do not, so they fall back
   * to the basic definition, preserving prior behavior).
   */
  private extractFieldsFromOpenApi(className: string): StateField[] | null {
    const schema = this.loadOpenApiSchema();
    const model = schema?.components?.schemas?.[className];
    const properties = model?.properties;
    if (!properties) return null;

    // Device-state heuristic — must look like it extends BaseDeviceState.
    if (!('last_command' in properties) || !('error' in properties)) return null;

    const required = new Set<string>(model.required || []);
    const fields: StateField[] = [];

    for (const [name, node] of Object.entries(properties as Record<string, any>)) {
      if (TS_BASE_STATE_FIELDS.has(name)) continue;
      fields.push({
        name,
        type: this.mapJsonSchemaToTypeScript(node),
        // Match the previous generator: device-specific fields are emitted as
        // required (the generated default object always provides a value).
        optional: false,
        description: `State field for ${name}`,
        defaultValue: 'default' in node ? node.default : (required.has(name) ? undefined : null),
      });
    }

    return fields;
  }

  /** Map a JSON Schema property node to a TypeScript type string. */
  private mapJsonSchemaToTypeScript(node: any): string {
    if (!node) return 'any';

    if (node.$ref) {
      // Referenced models aren't imported into the .state.ts file; keep it safe.
      return 'Record<string, any>';
    }

    if (Array.isArray(node.anyOf) || Array.isArray(node.oneOf)) {
      const variants = (node.anyOf || node.oneOf).map((n: any) => this.mapJsonSchemaToTypeScript(n));
      return Array.from(new Set(variants)).join(' | ');
    }

    if (Array.isArray(node.allOf) && node.allOf.length > 0) {
      return this.mapJsonSchemaToTypeScript(node.allOf[0]);
    }

    switch (node.type) {
      case 'string':
        return 'string';
      case 'integer':
      case 'number':
        return 'number';
      case 'boolean':
        return 'boolean';
      case 'null':
        return 'null';
      case 'array':
        return `${node.items ? this.mapJsonSchemaToTypeScript(node.items) : 'any'}[]`;
      case 'object':
        return 'Record<string, any>';
      default:
        return 'any';
    }
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