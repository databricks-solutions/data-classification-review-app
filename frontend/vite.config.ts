import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      '/api': `http://localhost:${process.env.BACKEND_PORT ?? '9005'}`,
    },
  },
  build: {
    // APX serves static assets from src/data_classification_review_app/__dist__/
    outDir: '../src/data_classification_review_app/__dist__',
    emptyOutDir: true,
  },
})
