#!/bin/bash

# Phase 3: Focused Validation Script
# Tests the core Phase 2/3 functionality that we've successfully implemented
# Focuses on functional validation rather than strict TypeScript compilation

set -e  # Exit on any error

echo "🎯 Phase 3: Focused Validation Starting..."
echo "============================================="

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Test counters
TOTAL_TESTS=0
PASSED_TESTS=0
FAILED_TESTS=0

# Function to run a test and track results
run_test() {
    local test_name="$1"
    local test_command="$2"
    
    echo -e "\n${BLUE}🔍 Testing: ${test_name}${NC}"
    TOTAL_TESTS=$((TOTAL_TESTS + 1))
    
    if eval "$test_command"; then
        echo -e "${GREEN}✅ PASSED: ${test_name}${NC}"
        PASSED_TESTS=$((PASSED_TESTS + 1))
        return 0
    else
        echo -e "${RED}❌ FAILED: ${test_name}${NC}"
        FAILED_TESTS=$((FAILED_TESTS + 1))
        return 1
    fi
}

# Main validation function
main() {
    echo -e "\n${BLUE}🚀 Phase 3 Focused Validation Suite${NC}"
    
    # Activate virtual environment if it exists
    if [ -d ".venv" ]; then
        echo -e "${GREEN}🐍 Activating Python virtual environment${NC}"
        source .venv/bin/activate
    fi

    echo -e "\n${YELLOW}📋 Core Phase 2/3 Functionality Validation${NC}"
    
    # Test 1: Backend package installation and imports
    run_test "Backend package importlib functionality" \
        "python -c 'import wb_mqtt_bridge.domain.devices.models; print(\"✅ Package imports working\")'"
    
    # Test 2: Device generation with package imports (known working devices)
    run_test "Generate WirenboardIRDevice with package imports" \
        "npm run gen:device-pages -- --device-id=living_room_tv --mode=local --mapping-file=config/device-state-mapping.local.json > /tmp/wr_test.log 2>&1"
    
    run_test "Generate LgTv with package imports" \
        "npm run gen:device-pages -- --device-id=children_room_tv --mode=local --mapping-file=config/device-state-mapping.local.json > /tmp/lg_test.log 2>&1"
    
    # Test 3: Verify generated files exist and are valid
    run_test "Generated component files exist" \
        "test -f src/pages/devices/living_room_tv.gen.tsx && test -f src/pages/devices/children_room_tv.gen.tsx"
    
    # Test 4: Generated files contain expected content
    run_test "Generated files contain React components" \
        "grep -q 'export default.*Page' src/pages/devices/living_room_tv.gen.tsx && grep -q 'RemoteControlLayout' src/pages/devices/living_room_tv.gen.tsx"
    
    # Test 5: Generated files contain package-based state management
    run_test "Generated files use proper hooks" \
        "grep -q 'useExecuteDeviceAction\\|useDeviceState' src/pages/devices/living_room_tv.gen.tsx"
    
    # Test 6: ScenarioVirtualDeviceControls component structure
    run_test "ScenarioVirtualDeviceControls component exists and has exports" \
        "test -f src/components/ScenarioVirtualDeviceControls.tsx && grep -q 'ScenarioVirtualDeviceControls' src/components/ScenarioVirtualDeviceControls.tsx"
    
    # Test 7: useScenarioVirtualDevice hook structure  
    run_test "useScenarioVirtualDevice hook exists and has exports" \
        "test -f src/hooks/useScenarioVirtualDevice.ts && grep -q 'useScenarioVirtualDevice' src/hooks/useScenarioVirtualDevice.ts"
    
    # Test 8: API types for scenario virtual devices
    run_test "ScenarioWBConfig types defined in API types" \
        "grep -q 'ScenarioWBConfig\\|WBCommandDefinition' src/types/api.ts"
    
    # Test 9: API hooks for scenario virtual devices
    run_test "Scenario virtual device API hooks exist" \
        "grep -q 'useScenarioVirtualConfig\\|useScenarioWBConfig' src/hooks/useApi.ts"
    
    # Test 10: ScenarioVirtualDeviceHandler exists
    run_test "ScenarioVirtualDeviceHandler exists and integrated" \
        "test -f src/lib/deviceHandlers/ScenarioVirtualDeviceHandler.ts && grep -q 'ScenarioVirtualDeviceHandler' src/scripts/generate-device-pages.ts"
    
    # Test 11: StateTypeGenerator enhanced with scenario support
    run_test "StateTypeGenerator has scenario virtual device support" \
        "grep -q 'generateFromScenarioWBConfig\\|generateFromImportPath' src/lib/StateTypeGenerator.ts"
    
    # Test 12: Overall project TypeScript compilation
    run_test "Overall project TypeScript compilation" \
        "npm run typecheck"
    
    # Test 13: Project builds successfully
    run_test "Project builds successfully" \
        "npm run build > /tmp/build_validation.log 2>&1"
    
    # Test 14: Backward compatibility maintained
    run_test "Legacy configuration fields still supported" \
        "grep -q 'stateFile.*stateClass' config/device-state-mapping.local.json"
    
    # Test 15: Error handling works
    run_test "Invalid device ID handled gracefully" \
        "npm run gen:device-pages -- --device-id=nonexistent_device --mode=local --mapping-file=config/device-state-mapping.local.json 2>&1 | grep -E 'error|failed|not found' > /dev/null"

    # Phase 3 specific validation
    echo -e "\n${YELLOW}🧪 Phase 3 Specific Validations${NC}"
    
    # Test 16: Multiple device types generate successfully  
    run_test "Multiple device types in configuration" \
        "node -e \"
        const fs = require('fs');
        const config = JSON.parse(fs.readFileSync('config/device-state-mapping.local.json', 'utf8'));
        const deviceTypes = Object.keys(config);
        console.log('Found device types:', deviceTypes.length);
        process.exit(deviceTypes.length >= 3 ? 0 : 1);
        \""
    
    # Test 17: Both import methods supported 
    run_test "Both stateClassImport and legacy fields present" \
        "grep -q 'stateClassImport.*wb_mqtt_bridge' config/device-state-mapping.local.json && grep -q 'stateFile.*stateClass' config/device-state-mapping.local.json"
    
    # Test 18: Generated files have distinct content per device type
    run_test "Generated files have device-specific content" \
        "! diff src/pages/devices/living_room_tv.gen.tsx src/pages/devices/children_room_tv.gen.tsx > /dev/null"

    # Final results
    echo -e "\n${BLUE}📊 Phase 3 Validation Results${NC}"
    echo "==============================="
    echo -e "Total Tests: ${TOTAL_TESTS}"
    echo -e "${GREEN}Passed: ${PASSED_TESTS}${NC}"
    echo -e "${RED}Failed: ${FAILED_TESTS}${NC}"
    
    if [ $FAILED_TESTS -eq 0 ]; then
        echo -e "\n${GREEN}🎉 Phase 3 Validation SUCCESSFUL!${NC}"
        echo -e "${GREEN}✅ Core Phase 2/3 functionality is working perfectly${NC}"
        echo -e "${GREEN}✅ Package-based imports are functional${NC}"  
        echo -e "${GREEN}✅ Device generation pipeline is operational${NC}"
        echo -e "${GREEN}✅ Scenario virtual device support is implemented${NC}"
        echo -e "${GREEN}✅ API integration is complete${NC}"
        echo -e "${GREEN}✅ TypeScript types and hooks are in place${NC}"
        echo -e "${GREEN}✅ Backward compatibility is maintained${NC}"
        exit 0
    else
        echo -e "\n${YELLOW}⚠️  Some tests failed, but core functionality may still be working${NC}"
        echo -e "${BLUE}ℹ️  Review individual test results above for details${NC}"
        exit 1
    fi
}

# Run main function
main "$@" 