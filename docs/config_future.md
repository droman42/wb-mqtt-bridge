# Future Configuration System Design

## Unified Configuration Model

This document outlines a comprehensive approach to redesigning the configuration system to address current inconsistencies and create a more maintainable architecture.

## Current Issues

The current configuration system has several inconsistencies:

1. Multiple naming conventions:
   - Device Implementation Class (e.g., "WirenboardIRDevice")
   - Device Type Identifier (e.g., "wirenboard_ir")
   - Config Class (e.g., WirenboardIRDeviceConfig)

2. Redundant identifiers in multiple files
   - system.json defines device_id mappings
   - Device config files contain their own device_id

3. No clear translation between naming conventions
   - The factory expects device types but receives class names

## Proposed Solution

### 1. Establish a Single Source of Truth

Create a unified configuration schema that eliminates redundancy:

```
devices: {
  "device_id": {
    "implementation": {
      "class": "WirenboardIRDevice",         // Implementation class
      "type": "wirenboard_ir"                // Device type for factory mapping
    },
    "config": {
      "name": "Musical Fidelity M6si",
      "alias": "amplifier",
      "mqtt_topic": "...",
      ...                                    // Device-specific config
    },
    "commands": { ... }                      // Commands configuration
  }
}
```

### 2. Define Clear Configuration Hierarchy

* System-level settings define global behavior
* Device-level settings define device-specific behavior
* Class-level defaults can be overridden by device-level settings

### 3. Create a Configuration Service

Introduce a dedicated service responsible for:
* Loading configuration from files
* Validating against schemas
* Building typed configurations for components
* Managing relationships between configuration entities

### 4. Use Dependency Injection

Components request their configuration from the service rather than directly accessing files:

```python
class DeviceFactory:
    def create_device(self, device_id, config_service):
        config = config_service.get_device_config(device_id)
        implementation_class = config_service.get_implementation_class(device_id)
        return implementation_class(config)
```

### 5. Implement Intelligent Type Resolution

Use a registry pattern to automatically discover and register device implementations and their corresponding configuration types.

### 6. Configuration Versioning & Migration

Add version information to configurations and include migration code to handle upgrades from older formats.

## Benefits

1. **Consistency**: One naming convention throughout the system
2. **Reduced redundancy**: Information defined in only one place
3. **Clear relationships**: Explicit connections between configurations
4. **Type safety**: Full use of Python's type system
5. **Maintainability**: Easier to understand and modify
6. **Extensibility**: Simple to add new device types

## Implementation Phases

1. Create the configuration service
2. Implement unified schema
3. Add migration tools for existing configs
4. Update device factory
5. Refactor existing components to use the new system

This approach requires more upfront investment but creates a maintainable system with clear separation of concerns, reduced redundancy, and elimination of the naming inconsistencies that caused the current issues. 