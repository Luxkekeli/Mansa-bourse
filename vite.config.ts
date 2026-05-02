import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  build: {
    target: 'esnext',
    rollupOptions: {
      // Si ton fichier index.html est à la racine, laisse simplement la ligne ci-dessous.
      // Si ton index.html est dans un dossier "frontend", remplace par 'frontend/index.html'
      input: 'frontend/app.html' 
    }
  }
})