import { defineConfig } from 'vite';
import { resolve } from 'path';

/**
 * P1-1 — Vite scaffold (NOT YET WIRED to the live frontend).
 *
 * This config builds the new `frontend/src/` modular tree into `frontend/dist/`.
 * The current `frontend/app.html` continues to be served as-is by Flask /
 * nginx until the migration is complete.
 *
 * Migration plan: see docs/VITE_MIGRATION.md.
 *
 * Run:
 *   npm install
 *   npm run build       # produces frontend/dist/
 *   npm run dev         # vite dev server with HMR on :5173
 */
export default defineConfig({
  root: 'frontend',
  publicDir: 'public',
  build: {
    outDir: 'dist',
    emptyOutDir: true,
    sourcemap: true,
    target: 'es2020',
    minify: 'esbuild',
    rollupOptions: {
      input: {
        main: resolve(__dirname, 'frontend/src/main.ts'),
      },
      output: {
        // Hashed filenames for cache-busting without manual SW invalidation.
        entryFileNames: 'assets/[name].[hash].js',
        chunkFileNames: 'assets/[name].[hash].js',
        assetFileNames: 'assets/[name].[hash][extname]',
      },
    },
    chunkSizeWarningLimit: 500,
  },
  server: {
    port: 5173,
    strictPort: false,
    proxy: {
      '/api': 'http://127.0.0.1:5000',
    },
  },
});
