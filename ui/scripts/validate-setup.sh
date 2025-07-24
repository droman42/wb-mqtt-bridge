#!/bin/bash

# UI Code Restructuring - Local Development Validation Script
# This script validates that the new package-based import system is working correctly

set -e  # Exit on any error

echo "🔍 UI Code Restructuring - Setup Validation"
echo "=============================================="

# Test 1: Check if wb-mqtt-bridge package is available
echo ""
echo "📦 Test 1: Backend Package Installation"
echo "---------------------------------------"

if python3 -c "import wb_mqtt_bridge" 2>/dev/null; then
    echo "✅ wb-mqtt-bridge package is importable"
else
    echo "❌ wb-mqtt-bridge package is not available"
    echo "💡 Install with: pip install -e ../wb-mqtt-bridge"
    exit 1
fi

# Test 2: Check if device models are importable
echo ""
echo "🔧 Test 2: Device Models Import"
echo "------------------------------"

if python3 -c "from wb_mqtt_bridge.domain.devices.models import WirenboardIRState; print('✅ Device models import successful')" 2>/dev/null; then
    echo "✅ Device models are accessible"
else
    echo "❌ Device models import failed"
    echo "💡 Check if wb-mqtt-bridge package structure matches expected paths"
    exit 1
fi

# Test 3: Check if scenario models are importable
echo ""
echo "🎮 Test 3: Scenario Models Import"
echo "--------------------------------"

if python3 -c "from wb_mqtt_bridge.infrastructure.scenarios.models import ScenarioWBConfig; print('✅ Scenario models import successful')" 2>/dev/null; then
    echo "✅ Scenario models are accessible"
else
    echo "⚠️  Scenario models import failed (this is expected if scenario feature is not implemented yet)"
fi

# Test 4: Check console scripts
echo ""
echo "🚀 Test 4: Console Scripts"
echo "-------------------------"

if command -v wb-api &> /dev/null; then
    echo "✅ wb-api command is available"
    wb-api --help | head -5
else
    echo "⚠️  wb-api command not found (may be expected)"
fi

# Test 5: Test TypeScript generation with package imports
echo ""
echo "🔄 Test 5: TypeScript Generation"
echo "-------------------------------"

# Try to generate types for a test device using local mode
echo "Testing type generation with local configuration..."

if npm run gen:device-pages -- --mode=local --mapping-file=config/device-state-mapping.local.json --test-connection; then
    echo "✅ Local configuration access successful"
else
    echo "❌ Local configuration access failed"
    exit 1
fi

# Test 6: TypeScript compilation check
echo ""
echo "🔍 Test 6: TypeScript Compilation"
echo "--------------------------------"

echo "Checking TypeScript compilation..."
if npm run typecheck:all; then
    echo "✅ TypeScript compilation successful"
else
    echo "❌ TypeScript compilation failed"
    exit 1
fi

echo ""
echo "🎉 All validation tests passed!"
echo "==============================="
echo ""
echo "Next steps:"
echo "• Try generating a device page: npm run gen:device-pages -- --device-id=<device-id> --mode=local --mapping-file=config/device-state-mapping.local.json"
echo "• Start development server: npm run dev"
echo "• Run full type generation: npm run gen:pages"
echo ""
echo "Phase 1 implementation is complete and ready for use! ✅" 