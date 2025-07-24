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
    proxy: {
      // API proxy for regular requests
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      // SSE proxy with special handling for text/event-stream
      '/events': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        ws: false, // Disable WebSocket upgrades for SSE
        // Critical: Configure proxy for SSE streaming
        configure(proxy) {
          proxy.on('proxyReq', (proxyReq, req) => {
            console.log('[Vite Proxy] SSE Request:', req.method, req.url);
            // Force SSE headers
            proxyReq.setHeader('Accept', 'text/event-stream');
            proxyReq.setHeader('Cache-Control', 'no-cache');
            proxyReq.setHeader('Connection', 'keep-alive');
          });
          
          proxy.on('proxyRes', (proxyRes, req, res) => {
            console.log('[Vite Proxy] SSE Response:', proxyRes.statusCode, proxyRes.headers['content-type']);
            
            // Force SSE response headers
            proxyRes.headers['content-type'] = 'text/event-stream';
            proxyRes.headers['cache-control'] = 'no-cache';
            proxyRes.headers['connection'] = 'keep-alive';
            proxyRes.headers['access-control-allow-origin'] = '*';
            proxyRes.headers['access-control-allow-headers'] = 'Cache-Control';
            
            // Disable buffering completely
            delete proxyRes.headers['content-length'];
            proxyRes.headers['x-accel-buffering'] = 'no';
          });
          
          proxy.on('error', (err, req, res) => {
            console.error('[Vite Proxy] SSE Error:', err);
          });
        },
        // Remove timeouts for persistent SSE connections
        timeout: 0,
        proxyTimeout: 0,
      },
    },
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