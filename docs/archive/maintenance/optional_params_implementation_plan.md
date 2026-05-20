# Optional Parameters Implementation Plan

This document provides a phased implementation plan for adding optional parameter support to device commands as outlined in `optional_params.md`. Each phase ends with a testable system to ensure smooth progression.

## Phase 1: Parameter Definition & Validation Infrastructure

This phase lays the groundwork for parameter handling without modifying existing behavior.

### Configuration & Schema Updates
- [x] Update Pydantic models in `app/schemas.py` to include parameter structures:
  - [x] Create `CommandParameterDefinition` model with required fields (`name`, `type`, `required`) and optional fields (`default`, `min`, `max`, `description`)
  - [x] Update `CommandConfig` model to include optional `params` field (array of `CommandParameterDefinition`)
  - [x] Ensure backward compatibility with existing configuration formats
- [x] Add tests for the new schema models

### Parameter Validation Utilities
- [x] Create parameter validation helper in `BaseDevice`:
  ```python
  def _resolve_and_validate_params(self, cmd_config: Dict, provided_params: Dict, raw_payload: Optional[str] = None) -> Dict:
      # Implementation
  ```
- [x] Implement validation logic:
  - [x] Extract parameter definitions from command config
  - [x] Set default values for optional parameters
  - [x] Validate required parameters exist
  - [x] Validate parameter types
  - [x] Validate min/max for range types
  - [x] Handle raw payload conversion for single-parameter commands
- [x] Add unit tests for the parameter validation helper

### Documentation
- [x] Create example configuration in documentation
- [x] Document parameter validation errors and handling

**Milestone 1:** ✅ Parameter validation infrastructure ready with tests, but not yet used in the execution flow.

## Phase 2: Update BaseDevice for Dual-Mode Operations

This phase modifies `BaseDevice` to support both old and new handler patterns simultaneously.

### Update `_execute_single_action` Method
- [x] Modify signature to include parameters and raw payload:
  ```python
  async def _execute_single_action(self, action_name: str, cmd_config: Dict[str, Any], params: Dict[str, Any], raw_payload: Optional[str] = None)
  ```
- [x] Implement handler compatibility wrapper:
  ```python
  def _call_action_handler(self, handler, cmd_config: Dict[str, Any], params: Dict[str, Any], raw_payload: Optional[str])
  ```
- [x] Update method to use the handler compatibility wrapper
- [x] Update `LastCommand` state to include parameter dictionary

### Update MQTT Message Handling
- [x] Modify `handle_message` to:
  - [x] Check for parameter definitions in the command
  - [x] Parse JSON payload when parameters are defined
  - [x] Handle single-value payload mapping for single-parameter commands
  - [x] Pass both raw payload and parsed parameters to `_execute_single_action`

### Update API Action Execution
- [x] Modify `execute_action` to:
  - [x] Validate parameters against the command definition
  - [x] Apply defaults for missing optional parameters
  - [x] Pass validated parameters to `_execute_single_action`

### Testing
- [x] Add integration tests for parameter handling via MQTT
- [x] Add integration tests for parameter handling via API
- [x] Verify backward compatibility with existing device handlers

**Milestone 2:** ✅ `BaseDevice` supports both old and new parameter patterns, with existing handlers continuing to work unchanged.

## Phase 3: Update Sample Device Implementation

Adapt one device to the new parameter system as a proof of concept.

### Select and Update a Simple Device
- [x] Choose a simple device for the first implementation (not BroadlinkKitchenHood)
  - Selected LG TV device (devices/lg_tv.py) as it already has parameters
- [x] Update device configuration to include parameter definitions
- [x] Update device handlers to use the new signature with parameters
- [x] Add tests for the updated device

### Documentation Update
- [x] Document the implementation process
- [x] Create a guide for migrating devices to the new system
- [x] Update example code snippets

**Milestone 3:** ✅ One device fully migrated to the new parameter system, proving the concept works.

## Phase 4: BroadlinkKitchenHood Implementation

Adapt the more complex BroadlinkKitchenHood device.

### Configuration Updates
- [x] Create new configuration format with `rf_codes` map
- [x] Define parameters for each command
- [x] Ensure configuration maintains backward compatibility

### Code Updates
- [x] Add logic to load the `rf_codes` map
- [x] Create consolidated handlers (`handle_set_light`, `handle_set_speed`)
- [x] Update handler registration
- [x] Maintain backward compatibility for legacy format

### Testing
- [x] Test legacy format operation
- [x] Test new parameter-based operation
- [x] Verify RF code map functionality

**Milestone 4:** ✅ Complex device working with new parameter system alongside backward compatibility.

## Phase 5: Migrate Remaining Devices

Systematically update all remaining devices.

### For Each Device:
- [x] Update configuration to include parameter definitions
- [x] Update handlers to use the new parameter signature
- [x] Add or update tests for parameter functionality
- [x] Verify both MQTT and API operation

### Document All Devices
- [x] Update device-specific documentation
- [x] Create examples for common parameter patterns

**Milestone 5:** ✅ All devices migrated to support parameters, with backward compatibility maintained.

## Phase 6: Testing and Stabilization

Comprehensive testing across the system.

### Integration Testing
- [x] Test all devices with different parameter combinations
- [x] Test MQTT and API interfaces
- [x] Test error handling for invalid parameters
- [x] Test edge cases for parameter validation

### Performance Testing
- [ ] Measure parameter validation overhead
- [ ] Identify optimization opportunities

### Documentation Finalization
- [ ] Finalize all documentation for parameter system
- [ ] Create user guide for configuring parameters

**Milestone 6:** ✅ System is stable and thoroughly tested with parameters throughout.

## Phase 7: Cleanup Transition Code

Remove backward compatibility once all devices are migrated.

### BaseDevice Cleanup
- [x] Simplify `_execute_single_action` to remove raw payload parameter
- [x] Remove handler compatibility wrapper
- [x] Update `handle_message` to only use parameter-based approach
- [x] Simplify `_resolve_and_validate_params` signature

### Device Implementation Cleanup
- [x] Standardize all handler signatures
- [x] Remove any legacy handlers or code
- [x] Update all device initialization code
- [x] **BroadlinkKitchenHood specific:**
  - [x] Remove legacy condition-based actions handling code
  - [x] Finalize transition to RF code map with parameters
  - [x] Remove any compatibility layers for old configuration format

### Configuration Cleanup
- [x] Review and clean up all device configurations
- [x] Enforce consistent parameter usage
- [ ] Remove backward compatibility code in Pydantic models (`app/schemas.py`)
- [ ] Remove any transition-specific types or optional fields

### Documentation Updates
- [ ] Update internal code documentation to reflect final implementation
- [ ] Remove references to deprecated patterns in comments and docstrings
- [ ] Ensure consistent documentation style across codebase

### Deployment Strategy
- [ ] Create a phased deployment plan for cleanup changes
- [ ] Prepare rollback procedures in case of unexpected issues
- [ ] Define criteria for successful deployment

### Monitoring and Logging
- [ ] Add specific logging for parameter validation and usage
- [ ] Implement monitoring for potential issues after cleanup
- [ ] Create alerts for parameter-related errors

### Final Code Review
- [ ] Perform comprehensive code review to ensure all backward compatibility code is removed
- [ ] Verify consistent implementation of parameter system across all devices
- [ ] Check that error handling is consistent and appropriate
- [ ] Ensure code style and documentation are up to standard

### Final Testing
- [ ] Comprehensive regression testing
- [ ] Verify all features work correctly
- [ ] Performance and load testing

**Milestone 7:** ✅ Clean, streamlined implementation with backward compatibility code removed.

## Phase 8: Release and Documentation

Finalize the implementation for release.

### Version Updates
- [ ] Update version numbers
- [ ] Create detailed release notes
- [ ] Document breaking changes

### Documentation Updates
- [ ] Ensure all documentation reflects final implementation
- [ ] Create migration guide for any external users
- [ ] Update API documentation

### Deployment
- [ ] Create deployment plan
- [ ] Plan for monitoring and rollback if needed

**Milestone 8:** ✅ Final release with complete documentation.

## Implementation Sequence Diagram

```
Phase 1: Parameter Definition & Validation Infrastructure
├── Update Pydantic models
├── Create validation utilities
└── Document parameter structures

Phase 2: Update BaseDevice for Dual-Mode Operations
├── Update _execute_single_action for dual-mode
├── Add handler compatibility wrapper
├── Update MQTT message handling
└── Update API action execution

Phase 3: Update Sample Device Implementation
├── Migrate simple device to new parameters
└── Document implementation process

Phase 4: BroadlinkKitchenHood Implementation
├── Update configuration with parameter definitions
├── Create consolidated handlers
└── Test both old and new approaches

Phase 5: Migrate Remaining Devices
└── Update all other devices one by one

Phase 6: Testing and Stabilization
├── Comprehensive integration testing
└── Documentation finalization

Phase 7: Cleanup Transition Code
├── Remove backward compatibility
└── Final regression testing

Phase 8: Release and Documentation
├── Version and documentation updates
└── Deployment planning
```

## Success Criteria

Each milestone has the following success criteria:

1. All tests pass
2. Existing functionality is preserved
3. New functionality works as expected
4. Documentation is updated
5. Code review is complete

## Resumption Context

If implementation is paused, refer to:

1. This implementation plan to identify the current phase
2. The `optional_params.md` document for technical details
3. The git history to see which checklist items have been completed
4. The test suite to verify the current state of the implementation

When resuming work:
1. Run the test suite to verify the current state
2. Review this document to identify the next steps
3. Check the milestone criteria to ensure proper progression 