// frontend/vite.config.js
import { defineConfig } from 'vite';
import vue from '@vitejs/plugin-vue';
import path from 'path'; // ← AJOUTÉ pour gérer les chemins absolus

export default defineConfig({
  plugins: [vue()],
  
  // ==============================
  // CONFIGURATION DES ALIAS (@ → src/)
  // ==============================
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'), // ← CLÉ DU FIX
    },
  },

  server: {
    host: '0.0.0.0',
    port: 5173,
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
        secure: false,
      },
    },
  },
});