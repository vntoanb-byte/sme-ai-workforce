import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import path from 'path'

export default defineConfig({
  plugins: [react()],
  resolve: { alias: { '@': path.resolve(__dirname, './src') } },
  server: {
    port: 5173,
    // Backend mặc định cổng 8080 (Makefile `make dev-api`); đổi bằng biến
    // VITE_API_TARGET nếu chạy backend ở cổng khác.
    proxy: { '/api': { target: process.env.VITE_API_TARGET ?? 'http://localhost:8080', changeOrigin: true } },
  },
  build: { outDir: 'dist' },
})
