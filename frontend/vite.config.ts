import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { VitePWA } from 'vite-plugin-pwa'

export default defineConfig({
  plugins: [
    react(),
    VitePWA({
      registerType: 'autoUpdate',
      manifest: {
        name: 'fluidGo',
        short_name: 'fluidGo',
        description: 'FluidPro Sales Intelligence Platform',
        theme_color: '#0A1628',
        background_color: '#F4F7FC',
        display: 'standalone',
        orientation: 'portrait-primary',
        start_url: '/',
        icons: [
          { src: '/icons/icon-192.png', sizes: '192x192', type: 'image/png' },
          { src: '/icons/icon-512.png', sizes: '512x512', type: 'image/png', purpose: 'any maskable' }
        ]
      },
      workbox: {
        runtimeCaching: [
          { urlPattern: /\/api\/dsr/, handler: 'NetworkFirst',
            options: { cacheName: 'dsr-cache', expiration: { maxAgeSeconds: 86400 } } },
          { urlPattern: /\/api\/analytics/, handler: 'StaleWhileRevalidate',
            options: { cacheName: 'analytics-cache' } },
          { urlPattern: /\/api\/meetings/, handler: 'NetworkFirst',
            options: { cacheName: 'meetings-cache' } }
        ]
      }
    })
  ],
  server: { host: true, port: 3000 },
  resolve: { alias: { '@': '/src' } }
})
