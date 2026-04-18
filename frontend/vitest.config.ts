import { defineConfig } from 'vitest/config';
import vue from '@vitejs/plugin-vue';
import { fileURLToPath, URL } from 'node:url';

/**
 * Vitest config — separate from vite.config.ts so the dev server doesn't
 * load test globals. Keeps prod bundles clean.
 *
 * Smoke tests live in src/**\/__tests__/*.test.ts (co-located with the code).
 * Nakijken Copilot v1 ships with tests for the grading inbox + detail views.
 */
export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: [],
    include: ['src/**/*.test.ts', 'src/**/__tests__/**/*.test.ts'],
    css: false,
  },
});
