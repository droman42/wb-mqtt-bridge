module.exports = {
  root: true,
  env: { browser: true, es2020: true },
  extends: [
    'eslint:recommended',
    'plugin:react-hooks/recommended',
  ],
  // 'wb-mqtt-bridge' is the sibling backend repo checked into the build context
  // (for device configs + openapi.json); it is not part of this app's lint scope.
  ignorePatterns: ['dist', '.eslintrc.cjs', 'wb-mqtt-bridge'],
  parser: '@typescript-eslint/parser',
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
  },
} 