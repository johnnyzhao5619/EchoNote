import { fileURLToPath, URL } from 'node:url'

import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import vueDevTools from 'vite-plugin-vue-devtools'
import { seoMetaPlugin } from './vite-plugins/seo-meta'

// https://vite.dev/config/
export default defineConfig({
  // Set base path for GitHub Pages deployment
  // Use environment variable or default to repository name
  base: process.env.VITE_BASE_PATH || '/EchoNote/',

  plugins: [vue(), vueDevTools(), seoMetaPlugin()],

  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },

  build: {
    rollupOptions: {
      output: {
        // Manual chunks for better caching
        manualChunks: {
          vendor: ['vue', 'vue-router', 'vue-i18n'],
        },
        // Asset file naming with type-based organization
        assetFileNames: (assetInfo) => {
          const fileName = assetInfo.names?.[0] || assetInfo.name || ''
          const getAssetType = (name: string): string => {
            if (/\.(mp4|webm|ogg|mp3|wav|flac|aac)(\?.*)?$/i.test(name)) return 'media'
            if (/\.(png|jpe?g|gif|svg|webp|avif)(\?.*)?$/i.test(name)) return 'images'
            if (/\.(woff2?|eot|ttf|otf)(\?.*)?$/i.test(name)) return 'fonts'
            return 'misc'
          }
          return `assets/${getAssetType(fileName)}/[name]-[hash][extname]`
        },
        chunkFileNames: 'assets/js/[name]-[hash].js',
        entryFileNames: 'assets/js/[name]-[hash].js',
      },
    },
  },
})
