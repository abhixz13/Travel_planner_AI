import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  server: {
    host: '0.0.0.0',
    port: 3000,
    strictPort: true,
    allowedHosts: [
      'voyage-planner-42.preview.emergentagent.com',
      '.preview.emergentagent.com'
    ],
  },
  build: {
    outDir: 'dist',
    sourcemap: false,
  },
});
