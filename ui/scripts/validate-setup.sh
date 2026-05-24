#!/bin/bash

# UI setup validation (monorepo). Confirms the UI can build against the sibling backend/
# contract. No Python / pip is needed — the API types come from backend/openapi.json
# (action_plan P1 #3.5). Layer 3 removed the build-time page generator; pages now render at
# runtime from the backend layout manifest, so there is no device/scenario codegen here.

set -e

echo "🔍 UI setup validation (monorepo)"
echo "================================="

# Test 1: backend contract file reachable (sibling backend/ in the monorepo)
echo ""
echo "📦 Test 1: Backend OpenAPI contract"
echo "-----------------------------------"
if [ -f "../backend/openapi.json" ]; then
    echo "✅ found ../backend/openapi.json"
else
    echo "❌ missing ../backend/openapi.json  (run this from ui/, with the monorepo backend/ present)"
    exit 1
fi

# Test 2: API types regenerate cleanly from the contract
echo ""
echo "🔄 Test 2: API types from the OpenAPI contract"
echo "----------------------------------------------"
npm run gen:api-types && echo "✅ src/types/api.gen.ts regenerated from ../backend/openapi.json"

# Test 3: typecheck + lint (CI parity)
echo ""
echo "🔍 Test 3: Typecheck + lint"
echo "---------------------------"
npm run check && echo "✅ check passed"

echo ""
echo "🎉 UI setup validated against the backend contract."
echo ""
echo "Next steps:"
echo "• Dev server:   npm run dev"
echo "• Regen types:  npm run gen:api-types   (after a backend API change)"
