import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { viteSingleFile } from 'vite-plugin-singlefile'

// Le build produit un SEUL fichier (JS + CSS inlines) ecrit dans
// ../web/console.html — servi tel quel par la route /console de Jarvis
// (core/operator.py). Aucun asset externe, aucun serveur Node requis.
export default defineConfig({
  plugins: [react(), viteSingleFile()],
  build: {
    outDir: 'dist',
    emptyOutDir: true,
    cssCodeSplit: false,
    assetsInlineLimit: 100000000,
    chunkSizeWarningLimit: 100000000,
  },
})
