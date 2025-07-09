# Strongly-Typed Configuration Implementation Plan

This document outlines a one-shot implementation plan for converting the current configuration system to a fully typed, strict model hierarchy.

## 1. Core Model Structure

### 1.1 Command Configuration Models

Create a clean hierarchy of command configuration models:

- **`BaseCommandConfig`**: Core abstract model with common fields:
  ```python
  action: Optional[str]
  topic: Optional[str]
  description: Optional[str]
  group: Optional[str]
  params: Optional[List[CommandParameterDefinition]] = None
  ```

- **`StandardCommandConfig`**: For devices with no special fields
  
- **`IRCommandConfig`**: For IR-controlled devices:
  ```python
  location: str
  rom_position: str
  ```

### 1.2 Device-Specific Parameter Models

Create models for device-specific parameters:

- **`RevoxA77ReelToReelParams`**:
  ```python
  sequence_delay: int = 5
  ```

- **`LgTvParams`**, **`EmotivaParams`**, etc. as needed

### 1.3 Device Configuration Models

Create a complete device configuration hierarchy:

- **`BaseDeviceConfig`**: Abstract base with common fields:
  ```python
  device_id: str
  device_name: str
  device_class: str
  
  ```

- **`WirenboardIRDeviceConfig`**:
  ```python
  commands: Dict[str, IRCommandConfig]
  ```

- **`RevoxA77ReelToReelConfig`**:
  ```python
  commands: Dict[str, IRCommandConfig]
  reel_to_reel: RevoxA77ReelToReelParams
  ```

- **`BroadlinkKitchenHoodConfig`**:
  ```python
  commands: Dict[str, StandardCommandConfig]
  rf_codes: Dict[str, Dict[str, str]]
  ```

- **`LgTvDeviceConfig`**:
  ```python
  commands: Dict[str, StandardCommandConfig]
  tv: LgTvConfig
  ```

- **`AppleTVDeviceConfig`**:
  ```python
  commands: Dict[str, StandardCommandConfig]
  apple_tv: AppleTVConfig
  ```

- **`EmotivaXMC2DeviceConfig`**:
  ```python
  commands: Dict[str, StandardCommandConfig]
  emotiva: EmotivaConfig
  ```

## 2. Configuration Loading System

Implement a robust type-safe configuration loading system:

1. **Configuration Factory**:
   - Create a `DeviceConfigFactory` that returns the appropriate config model based on device_class
   - Implement a strict mapping of device types to configuration models:
     ```python
     "wirenboard_ir": WirenboardIRDeviceConfig
     "RevoxA77ReelToReel": RevoxA77ReelToReelConfig
     "broadlink_kitchen_hood": BroadlinkKitchenHoodConfig
     "lg_tv": LgTvDeviceConfig
     "apple_tv_device": AppleTVDeviceConfig
     "emotiva_xmc2": EmotivaXMC2DeviceConfig
     ```

2. **Configuration Manager Updates**:
   - Update `ConfigManager` to use the factory for loading device configurations
   - Implement strict validation during loading

3. **Device Manager Updates**:
   - Update `DeviceManager` to work with strongly-typed configurations
   - Update device instantiation to pass type-specific configurations

## 3. Update Device Implementations

Update each device implementation to work with the new typed configurations:

1. **BaseDevice**:
   - Remove all backward compatibility code
   - Remove handling for legacy formats
   - Update to use strictly typed configurations

2. **RevoxA77ReelToReel**:
   - Update the RevoxA77ReelToReel device to use the already-renamed `reel_to_reel` field
   - Update the implementation to expect the field in this new location

3. **WirenboardIRDevice**:
   - Update to expect properly typed IR commands

4. **BroadlinkKitchenHood**:
   - Update to use typed Standard commands and separate rf_codes structure

5. **Other Device Classes**:
   - Update all implementations to use the appropriate typed models

## 4. Configuration File Verification

Verify all configuration files match the new format:

1. **Verify reel_to_reel.json**:
   - Confirm the `reel_to_reel` field is properly structured (already done)

2. **Verify all IR device configs**:
   - Make sure `location` and `rom_position` fields are present in all commands

3. **Verify BroadlinkKitchenHood config**:
   - Ensure the correct `rf_codes` structure

4. **Verify other device configs**:
   - Ensure all device configs match their respective model requirements

## 5. Schema Documentation

Create comprehensive schema documentation:

1. **Model Documentation**:
   - Document all models with clear descriptions
   - Include field validation requirements

2. **Configuration Guide**:
   - Create a guide for writing device configurations
   - Include examples for each device type

## 6. Testing and Validation

Implement comprehensive testing:

1. **Unit Tests**:
   - Create unit tests for all models
   - Test validation rules
   - Include specific tests for the RevoxA77ReelToReel with the `reel_to_reel` field

2. **Integration Tests**:
   - Test loading real configurations
   - Test device instantiation with typed configs

3. **Configuration Validators**:
   - Create validation tools to check configuration files

## 7. Implementation Steps

Execute the plan in this sequence:

1. Create all models in `app/schemas.py`
2. Implement the configuration factory
3. Update configuration loading in ConfigManager
4. Update device implementations to use typed configurations
5. Verify all configuration files comply with the new format
6. Update DeviceManager to use typed configurations
7. Run tests to validate the implementation
8. Update documentation

## 8. Classes Requiring Updates

1. **In app/schemas.py**:
   - Create all command and device configuration models
   - Remove `__getattr__` and `__getitem__` methods
   - Remove `extra = "allow"` from all models
   - Set strict validation for all models

2. **In app/config_manager.py**:
   - Add `DeviceConfigFactory`
   - Update configuration loading

3. **In app/device_manager.py**:
   - Update device instantiation with typed configs

4. **In devices/revox_a77_reel_to_reel.py**:
   - Update to use the renamed `reel_to_reel` field directly
   - Remove any code that looks for the legacy `parameters` field

5. **In all other device implementation classes**:
   - Update to work with typed configurations
   - Remove any backward compatibility code

## Summary

This plan creates a clean, type-safe model hierarchy for device configurations. By implementing this as a one-shot approach, we create a more maintainable system with clear type definitions for each device type. The plan acknowledges that the `reel_to_reel.json` configuration file has already been updated with the renamed field, and focuses on updating all code to work with this structure.

This approach removes all backward compatibility concerns, resulting in a more robust system with better type safety and validation. 