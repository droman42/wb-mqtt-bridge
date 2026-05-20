# Scenario System Upgrade Guide

## Overview

The scenario system has been enhanced with smarter transition logic and simplified configuration, which requires changes to the scenario configuration format. This document explains what has changed and how to upgrade your existing configurations.

## Changes Summary

1. **Flattened Shutdown Sequence**: 
   - The `shutdown_sequence` now uses a simple list instead of nested `complete`/`transition` sections
   - Smart device sharing detection now handles transitions automatically

2. **Power Command Detection**:
   - The system now intelligently detects and skips power commands for shared devices
   - This improves the user experience by avoiding unnecessary power cycles

3. **Conditional Commands**:
   - All commands now support the `condition` field to specify when they should execute
   - This is checked at runtime against the current device state

4. **Simplified Devices Format**:
   - The `devices` section is now a simple array of device IDs
   - Device capabilities are now retrieved from DeviceManager at runtime instead of being duplicated in scenario config

## Migration Process

### Automatic Migration

We provide a utility script to automatically migrate your scenario configurations:

```bash
# Create backups of original files (recommended)
python scripts/migrate_scenarios.py --backup

# Migrate without backups
python scripts/migrate_scenarios.py

# Specify a custom directory
python scripts/migrate_scenarios.py --directory=/path/to/scenarios
```

This script:
1. Processes all JSON files in the specified directory
2. Converts the shutdown sequence format
3. Simplifies the devices section format
4. Creates backups of the original files (optional)
5. Outputs a summary of the changes made

### Manual Migration

To manually migrate a scenario configuration:

1. Replace the nested `shutdown_sequence` structure with a flat list
2. Use the `complete` section as the new shutdown sequence
3. Convert the `devices` object to a simple array of device IDs
4. Ensure all commands have proper `condition` attributes

**Old Format:**
```json
"devices": {
  "tv": {
    "groups": ["screen", "volume_control"]
  },
  "receiver": {
    "groups": ["audio", "source_control"]
  }
},
"shutdown_sequence": {
  "complete": [
    {
      "device": "tv",
      "command": "power_off",
      "params": {},
      "condition": "device.power == True"
    }
  ],
  "transition": [
    {
      "device": "tv",
      "command": "set_input",
      "params": {"input": "hdmi1"}
    }
  ]
}
```

**New Format:**
```json
"devices": [
  "tv",
  "receiver"
],
"shutdown_sequence": [
  {
    "device": "tv",
    "command": "power_off",
    "params": {},
    "condition": "device.power == True"
  }
]
```

## Best Practices for Optimal Transitions

For the best experience with the new transition system:

1. **Add Clear Conditions**:
   - Always include conditions on power commands to avoid unnecessary state changes
   - Example: `"condition": "device.power != True"` for power_on commands
   - Example: `"condition": "device.power == True"` for power_off commands

2. **Include Input/Output Conditions**:
   - Condition input/output changes to run only when needed
   - Example: `"condition": "device.input != 'hdmi1'"`

3. **Consider Delays**:
   - Use `delay_after_ms` for devices that need time to stabilize
   - Example: `"delay_after_ms": 2000` for 2 seconds after power on

4. **Order of Operations**:
   - Order your commands logically (e.g., power on sources before displays)
   - Consider dependencies between devices

## Example Configuration

A reference implementation can be found in `config/scenarios/example.json`, showing all best practices.

## Need Help?

If you encounter any issues during migration:

1. Check that all required fields are present in your configuration
2. Verify that conditions are correctly formatted
3. Test your scenarios thoroughly after migration

For additional assistance, please refer to the full documentation or contact technical support. 