import js from '@eslint/js';
import tseslint from 'typescript-eslint';
import reactHooks from 'eslint-plugin-react-hooks';
import reactRefresh from 'eslint-plugin-react-refresh';
import globals from 'globals';

export default tseslint.config(
  // Lint scope = shipped app code (ts/tsx only, as the old `--ext ts,tsx` CLI scope did).
  // Excluded: 'wb-mqtt-bridge' (the sibling backend repo in the build context — configs +
  // openapi.json) and the plain-JS tooling files (jest/postcss/tailwind configs, scripts/).
  {
    ignores: ['dist', 'wb-mqtt-bridge', '**/*.js', '**/*.mjs', '**/*.cjs'],
  },
  {
    files: ['**/*.{ts,tsx}'],
    extends: [
      js.configs.recommended,
      // recommendedTypeChecked is a superset of recommended; type-aware rules
      // (no-floating-promises, no-misused-promises, await-thenable, ...) require
      // parserOptions.project below — this is what catches the bugs `tsc` + plain lint miss.
      ...tseslint.configs.recommendedTypeChecked,
      reactHooks.configs['recommended-latest'],
    ],
    languageOptions: {
      ecmaVersion: 2020,
      globals: { ...globals.browser, ...globals.es2020 },
      parserOptions: {
        // every linted file must belong to one of these projects for type-aware rules to resolve.
        // tsconfig.json = app code (incl. IconResolver + the type files);
        // tsconfig.node.json = vite.config.ts.
        project: ['./tsconfig.json', './tsconfig.node.json'],
        tsconfigRootDir: import.meta.dirname,
      },
    },
    plugins: {
      'react-refresh': reactRefresh,
    },
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
          argsIgnorePattern: '^_',
          varsIgnorePattern: '^_',
          ignoreRestSiblings: true,
          args: 'none', // Don't check function/method parameters
        },
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
  },
);
