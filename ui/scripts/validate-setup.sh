#!/bin/bash

# UI setup validation (monorepo). Confirms the UI can build against the sibling backend/
# contract. No Python / pip is needed — device-state types come from backend/openapi.json,
# not from importing the backend package (action_plan P1 #3.5).

set -e

echo "🔍 UI setup validation (monorepo)"
echo "================================="

# Test 1: backend contract files reachable (sibling backend/ in the monorepo)
echo ""
echo "📦 Test 1: Backend contract files"
echo "---------------------------------"
for f in ../backend/openapi.json ../backend/config/device-state-mapping.json; do
    if [ -f "$f" ]; then
        echo "✅ found $f"
    else
        echo "❌ missing $f  (run this from ui/, with the monorepo backend/ present)"
        exit 1
    fi
done

# Test 2: API types regenerate cleanly from the contract
echo ""
echo "🔄 Test 2: API types from the OpenAPI contract"
echo "----------------------------------------------"
npm run gen:api-types && echo "✅ src/types/api.gen.ts regenerated from ../backend/openapi.json"

# Test 3: device + scenario page codegen (reads ../backend)
echo ""
echo "🎮 Test 3: Device + scenario codegen"
echo "------------------------------------"
npm run gen:device-pages -- --batch --mode=local \
    --mapping-file=../backend/config/device-state-mapping.json --generate-router \
    && echo "✅ codegen succeeded"

# Test 4: TypeScript compiles
echo ""
echo "🔍 Test 4: TypeScript compilation"
echo "---------------------------------"
npm run typecheck:all && echo "✅ typecheck passed"

echo ""
echo "🎉 UI setup validated against the backend contract."
echo ""
echo "Next steps:"
echo "• Dev server:        npm run dev"
echo "• Full codegen:      npm run gen:device-pages -- --batch --mode=local --mapping-file=../backend/config/device-state-mapping.json --generate-router"
