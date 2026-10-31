import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';

// Em desenvolvimento (`npm run dev`), as rotas do harness vão para o servidor dele; em produção o próprio harness serve o
// build (`dist/`) na mesma origem, sem proxy nenhum.
const HARNESS = process.env.HARNESS_URL || 'http://127.0.0.1:7860';

export default defineConfig({
  plugins: [react()],
  server: {
    host: '127.0.0.1',
    proxy: {
      '/entrar': HARNESS,
      '/sair': HARNESS,
      '/sessao': HARNESS,
      '/voz': HARNESS,
      '/newclaw': HARNESS,
      '/api/offer': HARNESS,
    },
  },
  // ~620 kB, quase tudo do cliente WebRTC do Pipecat (daily-js); servido pelo harness na própria máquina.
  build: { outDir: 'dist', sourcemap: false, chunkSizeWarningLimit: 800 },
  test: { environment: 'node', include: ['src/**/*.test.ts', 'src/**/*.test.tsx'] },
});
