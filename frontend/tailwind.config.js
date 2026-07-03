/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        // ── fluidPro / WEPSol Brand Palette (extracted from official logos) ──
        // fluidPro primary purple — wordmark colour
        'brand-purple':  '#92278E',
        'brand-purple-lt':'#F3E6F3',
        // fluidPro pink/red — stripe accent colour
        'brand-pink':    '#F0115E',
        'brand-pink-lt': '#FDE8F0',
        // fluidPro grey — secondary stripe
        'brand-grey':    '#808083',
        // WEPSol multi-brand dots
        'wep-dot-green':  '#4AAB29',
        'wep-dot-orange': '#FF4C01',
        'wep-dot-yellow': '#FDD207',
        'wep-dot-indigo': '#48439C',
        'wep-dot-teal':   '#56BA93',

        // ── Application semantic colours ──────────────────────────────────────
        // Interactive / CTA — use fluidPro pink (brand action colour)
        'wep-orange':    '#F0115E',   // renamed but kept for compat — now brand-pink
        'wep-orange-lt': '#FDE8F0',

        // App navigation background
        'wep-navy':      '#1A0B2E',   // deep purple-navy (fluidPro purple darkened)
        'wep-blue':      '#2D1B6E',   // secondary purple

        // Interactive blue for data actions
        'wep-accent':    '#1E6FD9',
        'wep-electric':  '#0EA5E9',
        'wep-teal':      '#0D9488',
        'wep-amber':     '#D97706',
        'wep-red':       '#DC2626',
        'wep-green':     '#059669',

        // Layout
        'wep-surface':   '#F8F5FF',   // very light purple tint for page bg
        'wep-card':      '#FFFFFF',
        'wep-border':    '#E8DFF5',   // purple-tinted border
        'wep-border-strong': '#C8B4E8',
        'wep-muted':     '#6B5F7A',
        'wep-light':     '#9B8FAB',
        'wep-text':      '#1A0B2E',
      },
      fontFamily: {
        sans:    ['Inter', 'system-ui', 'sans-serif'],
        display: ['Syne', 'Inter', 'sans-serif'],
      },
      boxShadow: {
        'card':     '0 1px 3px rgba(26,11,46,0.07), 0 1px 2px rgba(26,11,46,0.04)',
        'card-md':  '0 4px 12px rgba(26,11,46,0.10)',
        'card-lg':  '0 8px 24px rgba(26,11,46,0.13)',
        'pink':     '0 4px 14px rgba(240,17,94,0.35)',
        'purple':   '0 4px 14px rgba(146,39,142,0.30)',
        'blue':     '0 4px 14px rgba(30,111,217,0.30)',
      },
      backgroundImage: {
        // Sidebar gradient — deep purple (fluidPro identity)
        'sidebar-gradient': 'linear-gradient(180deg, #1A0B2E 0%, #2D1452 100%)',
        // CTA gradient — brand pink (fluidPro stripe colour)
        'cta-gradient':     'linear-gradient(135deg, #F0115E 0%, #C2005A 100%)',
        // Page header gradient
        'header-gradient':  'linear-gradient(135deg, #1A0B2E 0%, #3D1A6E 100%)',
        // Login page
        'login-gradient':   'linear-gradient(135deg, #1A0B2E 0%, #2D1B6E 60%, #1A0B2E 100%)',
      },
    },
  },
  plugins: [],
}
