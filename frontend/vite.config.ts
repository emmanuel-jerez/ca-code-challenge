import react from '@vitejs/plugin-react';
import { Version } from 'sass';
import { defineConfig } from 'vitest/config';

// The same deprecation policy as the `scss` script: every deprecation active in
// the pinned Sass version is an error (ADR 0023).
const SASS_FATAL_DEPRECATIONS = Version.parse('1.107.0');

export default defineConfig(({ command }) => ({
  plugins: [react()],
  // Where Django serves the build (STATICFILES_DIRS, ADR 0032). The dev
  // page stays at the root.
  base: command === 'build' ? '/static/frontend/' : '/',
  build: {
    outDir: 'dist',
    manifest: true,
    // Never inline assets as data: URIs; the CSP allows only 'self' (ADR 0017).
    assetsInlineLimit: 0,
    // modulepreload is widely supported; the polyfill would be dead code.
    modulePreload: { polyfill: false },
    rolldownOptions: {
      // The island entry. It imports no CSS: the page links theme.css.
      input: { brandList: 'src/brand-list/main.tsx' },
    },
  },
  css: {
    preprocessorOptions: {
      scss: { fatalDeprecations: [SASS_FATAL_DEPRECATIONS] },
    },
  },
  server: {
    // Keep the dev server on localhost: every recent Vite advisory is a
    // dev-server one.
    host: 'localhost',
    proxy: { '/api': 'http://localhost:8000' },
  },
  test: {
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
    unstubGlobals: true,
    restoreMocks: true,
  },
}));
