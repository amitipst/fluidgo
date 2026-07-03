import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import { VitePWA } from 'vite-plugin-pwa'

export default defineConfig({
  plugins: [
    react(),
    VitePWA({
      registerType: 'autoUpdate',
      manifest: {
        name: 'fluidGo — WEP Solutions',
        short_name: 'fluidGo',
        description: 'WEP Solutions Sales Intelligence Platform — AI-powered DSR, BANT scoring, FGA workflow',
        theme_color: '#92278E',
        background_color: '#F8F5FF',
        display: 'standalone',
        orientation: 'portrait-primary',
        start_url: '/',
        icons: [
          { src: '/fluidgo-icon.svg', sizes: 'any', type: 'image/svg+xml', purpose: 'any maskable' },
          { src: '/icon-192.png', sizes: '192x192', type: 'image/png' },
          { src: '/icon-512.png', sizes: '512x512', type: 'image/png', purpose: 'any maskable' }
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
  server: {
    host: '0.0.0.0',
    port: 3000,
    // Vite 5.x: allowedHosts must be true (boolean) or an array to disable host check
    // 'all' as string is NOT valid — use true to allow all hosts
    allowedHosts: true as any,
    strictPort: true,
    hmr: {
      clientPort: 80,
    },
  },
  resolve: { alias: { '@': '/src' } }
})
