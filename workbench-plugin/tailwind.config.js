import preset from 'locveil-ui-kit/preset'

/** @type {import('tailwindcss').Config} */
export default {
  // Locveil preset; tokens.css + the single Tailwind preflight are loaded by the
  // WORKBENCH SHELL (HK-11) — plugin builds ship neither. The kit's dist is scanned
  // so utility classes inside kit components are generated into the plugin css.
  presets: [preset],
  corePlugins: {
    preflight: false,
  },
  content: [
    './src/**/*.{js,jsx,ts,tsx}',
    './node_modules/locveil-ui-kit/dist/**/*.js',
  ],
  theme: {
    extend: {},
  },
  plugins: [],
}
