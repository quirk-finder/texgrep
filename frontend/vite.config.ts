import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    host: '0.0.0.0',
    watch: {
      // これが重要。Docker/Windows ではポーリングにする
      usePolling: true,
      interval: 200, // 200-500ms くらいでOK
    },
    hmr: {
      // ブラウザが接続するポート。ポート転送している 5173 を明示
      clientPort: 5173,
    },
    proxy: {
      '/api': {
        target: 'http://backend:8000',
        changeOrigin: true
      }
    }
  }
});
