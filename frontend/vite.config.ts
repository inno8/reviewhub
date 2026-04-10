import { defineConfig } from 'vite';
import vue from '@vitejs/plugin-vue';
import { fileURLToPath, URL } from 'node:url';

export default defineConfig({
  plugins: [vue()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
    // Prefer TypeScript over stale co-located .js artifacts (e.g. router/index.js shadowing index.ts)
    extensions: ['.ts', '.tsx', '.vue', '.mts', '.js', '.jsx', '.mjs', '.json'],
  },
});
