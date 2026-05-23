module.exports = {
  root: true,
  env: { browser: true, es2020: true },
  extends: [
    'eslint:recommended',
    'plugin:react-hooks/recommended',
    'plugin:@typescript-eslint/recommended',
    // type-aware rules (no-floating-promises, no-misused-promises, await-thenable, ...) —
    // require parserOptions.project below; this is what catches the bugs `tsc` + plain lint miss.
    'plugin:@typescript-eslint/recommended-type-checked',
  ],
  // Lint scope = shipped app code (mirrors tsconfig.json's typecheck scope). Excluded:
  //  - 'wb-mqtt-bridge': the sibling backend repo in the build context (configs + openapi.json).
  //  - '*.gen.tsx': generated device/scenario pages — no tsconfig project, built fresh in CI,
  //    retired by Layer 3 (type-aware lint would error "not in a project").
  //  - the build-time codegen tooling (src/scripts, src/lib/{validation,generators,deviceHandlers,
  //    integration} + the individual lib utilities): not shipped, still covered by `typecheck:scripts`,
  //    and deleted at Layer 3 Step 4 — not worth tightening dead code.
  ignorePatterns: [
    'dist', '.eslintrc.cjs', 'wb-mqtt-bridge', 'src/**/*.gen.tsx',
    'src/scripts/**', 'src/lib/validation/**', 'src/lib/generators/**',
    'src/lib/deviceHandlers/**', 'src/lib/integration/**',
    'src/lib/BatchProcessor.ts', 'src/lib/DataValidator.ts', 'src/lib/DeviceConfigurationClient.ts',
    'src/lib/DocumentationGenerator.ts', 'src/lib/ErrorHandler.ts', 'src/lib/PerformanceMonitor.ts',
    'src/lib/StateTypeGenerator.ts',
  ],
  parser: '@typescript-eslint/parser',
  parserOptions: {
    // every linted file must belong to one of these projects for type-aware rules to resolve.
    // tsconfig.json = app code (incl. IconResolver + the type files, now un-excluded);
    // tsconfig.node.json = vite.config.ts.
    project: ['./tsconfig.json', './tsconfig.node.json'],
    tsconfigRootDir: __dirname,
  },
  plugins: ['react-refresh', '@typescript-eslint'],
  rules: {
    'react-refresh/only-export-components': [
      'warn',
      { allowConstantExport: true },
    ],
    // Disable base ESLint no-unused-vars and use TypeScript version
    'no-unused-vars': 'off',
    '@typescript-eslint/no-unused-vars': [
      'error',
      {
        'argsIgnorePattern': '^_',
        'varsIgnorePattern': '^_',
        'ignoreRestSiblings': true,
        'args': 'none' // Don't check function/method parameters
      }
    ],
    '@typescript-eslint/no-explicit-any': 'off',
    '@typescript-eslint/ban-ts-comment': 'off',
    'prefer-const': 'off',
    '@typescript-eslint/no-non-null-assertion': 'off',

    // --- type-aware tuning ---
    // The no-unsafe-* family + restrict-template-expressions fire constantly in a codebase that
    // intentionally allows `any` (no-explicit-any is off above); they'd bury the signal. Keep the
    // high-value async/correctness rules from recommended-type-checked, drop the `any`-noise ones.
    '@typescript-eslint/no-unsafe-assignment': 'off',
    '@typescript-eslint/no-unsafe-member-access': 'off',
    '@typescript-eslint/no-unsafe-call': 'off',
    '@typescript-eslint/no-unsafe-return': 'off',
    '@typescript-eslint/no-unsafe-argument': 'off',
    '@typescript-eslint/restrict-template-expressions': 'off',
    '@typescript-eslint/no-redundant-type-constituents': 'off',
    // un-awaited promises are a real bug class (esp. in fetch-and-render code); keep as errors.
    '@typescript-eslint/no-floating-promises': 'error',
    '@typescript-eslint/no-misused-promises': 'error',
  },
}
