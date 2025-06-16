import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import { fileURLToPath } from 'url';

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': fileURLToPath(new globalThis.URL('./src', import.meta.url)),
    },
  },
  server: {
    host: true,
    port: 3000,
  },
  build: {
    target: 'esnext',
    rollupOptions: {
      output: {
        manualChunks: {
          vendor: ['react', 'react-dom'],
          router: ['react-router-dom'],
          state: ['zustand', 'immer'],
          query: ['@tanstack/react-query'],
          i18n: ['react-i18next', 'i18next'],
        },
      },
    },
  },
}); 