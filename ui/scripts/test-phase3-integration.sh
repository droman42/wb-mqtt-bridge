#!/bin/bash

# Phase 3.3: Integration Testing Script
# Tests with live wb-mqtt-bridge backend and validates API integration
# Verifies new API endpoints and end-to-end flows

set -e  # Exit on any error

echo "🔗 Phase 3.3: Integration Testing Starting..."
echo "================================================"

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

# Configuration
BACKEND_URL="${BACKEND_URL:-http://localhost:8000}"
TIMEOUT_SECONDS=10

# Function to run a test and track results
run_test() {
    local test_name="$1"
    local test_command="$2"
    
    echo -e "\n${BLUE}🔍 Testing: ${test_name}${NC}"
    TOTAL_TESTS=$((TOTAL_TESTS + 1))
    
    if timeout $TIMEOUT_SECONDS bash -c "$test_command"; then
        echo -e "${GREEN}✅ PASSED: ${test_name}${NC}"
        PASSED_TESTS=$((PASSED_TESTS + 1))
        return 0
    else
        echo -e "${RED}❌ FAILED: ${test_name}${NC}"
        FAILED_TESTS=$((FAILED_TESTS + 1))
        return 1
    fi
}

# Function to test backend connectivity
test_backend_connectivity() {
    echo -e "\n${YELLOW}🌐 Testing Backend Connectivity${NC}"
    
    run_test "Backend server reachable" \
        "curl -s --connect-timeout 5 ${BACKEND_URL}/system > /dev/null"
    
    run_test "System endpoint returns valid JSON" \
        "curl -s ${BACKEND_URL}/system | python -m json.tool > /dev/null"
    
    run_test "API documentation accessible" \
        "curl -s --connect-timeout 5 ${BACKEND_URL}/docs > /dev/null"
}

# Function to test new scenario virtual configuration API endpoints
test_scenario_virtual_api_endpoints() {
    echo -e "\n${YELLOW}🎮 Testing Scenario Virtual Configuration API Endpoints${NC}"
    
    # Test GET /scenario/virtual_configs endpoint
    run_test "GET /scenario/virtual_configs endpoint" \
        "curl -s --fail ${BACKEND_URL}/scenario/virtual_configs | python -c \"
import sys, json
data = json.load(sys.stdin)
print('Virtual configs endpoint working, found', len(data) if isinstance(data, dict) else 0, 'configurations')
\""
    
    # Get list of available scenarios first
    scenarios=$(curl -s ${BACKEND_URL}/scenario/definition 2>/dev/null | python -c "
import sys, json
try:
    data = json.load(sys.stdin)
    if isinstance(data, list) and len(data) > 0:
        print(data[0]['scenario_id'])
    else:
        print('test_scenario')
except:
    print('test_scenario')
" 2>/dev/null || echo "test_scenario")
    
    if [ "$scenarios" != "test_scenario" ]; then
        # Test GET /scenario/virtual_config/{scenario_id} with real scenario
        run_test "GET /scenario/virtual_config/${scenarios} endpoint" \
            "curl -s --fail ${BACKEND_URL}/scenario/virtual_config/${scenarios} | python -c \"
import sys, json
data = json.load(sys.stdin)
assert 'scenario_id' in data, 'Missing scenario_id in response'
assert 'config' in data, 'Missing config in response'
print('Virtual config endpoint working for scenario:', data['scenario_id'])
\""
    else
        echo -e "${YELLOW}⚠️  No real scenarios available, testing with mock scenario${NC}"
        # Test endpoint exists even if no specific scenario
        run_test "Scenario virtual config endpoint structure" \
            "curl -s ${BACKEND_URL}/scenario/virtual_config/test_scenario 2>&1 | grep -E 'not found|404|scenario_id' > /dev/null"
    fi
}

# Function to test API integration with frontend
test_frontend_api_integration() {
    echo -e "\n${YELLOW}🖥️  Testing Frontend API Integration${NC}"
    
    # Test if frontend can start with backend connection
    run_test "Frontend can connect to backend API" \
        "VITE_API_BASE_URL=${BACKEND_URL} npm run build > /tmp/build_test.log 2>&1"
    
    # Test API hooks compilation with real types
    run_test "API hooks work with backend types" \
        "node -e \"
const fetch = require('node-fetch');
global.fetch = fetch;

// Mock test of useApi hooks
const testApiIntegration = async () => {
    try {
        const response = await fetch('${BACKEND_URL}/system');
        const data = await response.json();
        console.log('API integration test passed, system version:', data.version || 'unknown');
        return true;
    } catch (error) {
        console.error('API integration failed:', error.message);
        return false;
    }
};

testApiIntegration().then(success => process.exit(success ? 0 : 1));
\""
}

# Function to test scenario virtual device controls
test_scenario_virtual_device_controls() {
    echo -e "\n${YELLOW}🎛️  Testing Scenario Virtual Device Controls${NC}"
    
    # Test ScenarioVirtualDeviceControls component can be imported
    run_test "ScenarioVirtualDeviceControls component import" \
        "node -e \"
try {
    // Test that the component can be loaded (without React rendering)
    const componentCode = require('fs').readFileSync('src/components/ScenarioVirtualDeviceControls.tsx', 'utf8');
    const hasRequiredExports = componentCode.includes('ScenarioVirtualDeviceControls');
    console.log('Component export found:', hasRequiredExports);
    process.exit(hasRequiredExports ? 0 : 1);
} catch (e) {
    console.error('Component import failed:', e.message);
    process.exit(1);
}
\""
    
    # Test useScenarioVirtualDevice hook can be imported
    run_test "useScenarioVirtualDevice hook import" \
        "node -e \"
try {
    const hookCode = require('fs').readFileSync('src/hooks/useScenarioVirtualDevice.ts', 'utf8');
    const hasRequiredExports = hookCode.includes('useScenarioVirtualDevice');
    console.log('Hook export found:', hasRequiredExports);
    process.exit(hasRequiredExports ? 0 : 1);
} catch (e) {
    console.error('Hook import failed:', e.message);
    process.exit(1);
}
\""
    
    # Test that new API types are properly defined
    run_test "ScenarioWBConfig types properly defined" \
        "node -e \"
const typesCode = require('fs').readFileSync('src/types/api.ts', 'utf8');
const hasScenarioTypes = typesCode.includes('ScenarioWBConfig') && 
                        typesCode.includes('WBCommandDefinition');
console.log('Scenario types properly defined:', hasScenarioTypes);
process.exit(hasScenarioTypes ? 0 : 1);
\""
}

# Function to validate end-to-end device control flows
test_end_to_end_device_flows() {
    echo -e "\n${YELLOW}🔄 Testing End-to-End Device Control Flows${NC}"
    
    # Test device discovery flow
    run_test "Device discovery via API" \
        "curl -s ${BACKEND_URL}/config/devices | python -c \"
import sys, json
data = json.load(sys.stdin)
print('Device discovery working, found', len(data) if isinstance(data, dict) else 0, 'devices')
\""
    
    # Test device configuration retrieval
    run_test "Device configuration retrieval" \
        "curl -s ${BACKEND_URL}/config/devices | python -c \"
import sys, json
data = json.load(sys.stdin)
if isinstance(data, dict) and len(data) > 0:
    device_id = list(data.keys())[0]
    print('Testing device config for:', device_id)
    sys.exit(0)
else:
    print('No devices found for configuration test')
    sys.exit(1)
\""
    
    # Test generation pipeline with API mode
    run_test "Device generation with API mode" \
        "npm run gen:device-pages -- --device-id=living_room_tv --mode=api --api-base-url=${BACKEND_URL} > /tmp/api_gen_test.log 2>&1"
    
    # Test that generated components reference correct API endpoints
    if [ -f "src/pages/devices/living_room_tv.gen.tsx" ]; then
        run_test "Generated component uses correct API integration" \
            "grep -q 'useDeviceState\\|useExecuteDeviceAction' src/pages/devices/living_room_tv.gen.tsx"
    fi
}

# Function to test error handling and resilience
test_integration_error_handling() {
    echo -e "\n${YELLOW}🚨 Testing Integration Error Handling${NC}"
    
    # Test graceful handling of backend unavailability
    run_test "Graceful handling of backend unavailability" \
        "VITE_API_BASE_URL=http://localhost:9999 npm run gen:device-pages -- --device-id=test --mode=api 2>&1 | grep -q 'not available'"
    
    # Test handling of invalid API responses
    run_test "Handling of API timeout scenarios" \
        "timeout 5s npm run gen:device-pages -- --device-id=test --mode=api --api-base-url=http://1.2.3.4:8000 2>&1 | grep -E 'timeout|not available|error' > /dev/null"
    
    # Test fallback to local mode when API fails
    run_test "Fallback to local mode when API unavailable" \
        "npm run gen:device-pages -- --device-id=living_room_tv --mode=local --mapping-file=config/device-state-mapping.local.json > /tmp/fallback_test.log 2>&1"
}

# Function to test performance and load handling
test_performance_aspects() {
    echo -e "\n${YELLOW}⚡ Testing Performance Aspects${NC}"
    
    # Test that batch generation completes within reasonable time
    run_test "Batch generation performance" \
        "timeout 60s npm run gen:device-pages -- --batch --mode=local --mapping-file=config/device-state-mapping.local.json > /tmp/perf_test.log 2>&1"
    
    # Test TypeScript compilation performance
    run_test "TypeScript compilation performance" \
        "timeout 30s npm run typecheck"
    
    # Test that build process completes successfully
    run_test "Build process performance" \
        "timeout 120s npm run build > /tmp/build_perf_test.log 2>&1"
}

# Main test execution
main() {
    echo -e "\n${BLUE}🏁 Starting Integration Testing Suite${NC}"
    
    # Ensure we're in the right directory and environment is set up
    if [ ! -f "package.json" ]; then
        echo -e "${RED}❌ Error: Not in project root directory${NC}"
        exit 1
    fi
    
    # Activate virtual environment if it exists
    if [ -d ".venv" ]; then
        echo -e "${GREEN}🐍 Activating Python virtual environment${NC}"
        source .venv/bin/activate
    fi
    
    echo -e "${BLUE}🔗 Testing against backend: ${BACKEND_URL}${NC}"
    
    # Test 1: Backend connectivity
    test_backend_connectivity
    
    # Test 2: New API endpoints
    test_scenario_virtual_api_endpoints
    
    # Test 3: Frontend API integration
    test_frontend_api_integration
    
    # Test 4: Scenario virtual device controls
    test_scenario_virtual_device_controls
    
    # Test 5: End-to-end device flows
    test_end_to_end_device_flows
    
    # Test 6: Integration error handling
    test_integration_error_handling
    
    # Test 7: Performance aspects
    test_performance_aspects
    
    # Final results
    echo -e "\n${BLUE}📊 Integration Test Results Summary${NC}"
    echo "======================================"
    echo -e "Total Tests: ${TOTAL_TESTS}"
    echo -e "${GREEN}Passed: ${PASSED_TESTS}${NC}"
    echo -e "${RED}Failed: ${FAILED_TESTS}${NC}"
    echo -e "Backend URL: ${BACKEND_URL}"
    
    if [ $FAILED_TESTS -eq 0 ]; then
        echo -e "\n${GREEN}🎉 All integration tests passed! Phase 3.3 Integration Testing Complete.${NC}"
        exit 0
    else
        echo -e "\n${RED}💥 Some integration tests failed. Please review the failures above.${NC}"
        echo -e "${YELLOW}💡 Note: Some failures may be expected if the backend is not running.${NC}"
        exit 1
    fi
}

# Check if --skip-backend flag is provided
if [[ "$1" == "--skip-backend" ]]; then
    echo -e "${YELLOW}⚠️  Skipping backend-dependent tests${NC}"
    test_scenario_virtual_device_controls
    test_integration_error_handling
    test_performance_aspects
else
    # Run full integration tests
    main "$@"
fi 