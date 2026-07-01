/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        'wep-navy':    '#0A1628',
        'wep-blue':    '#1A3A6B',
        'wep-accent':  '#0078D4',
        'wep-electric':'#00B4E6',
        'wep-teal':    '#00C2A8',
        'wep-amber':   '#F5A623',
        'wep-red':     '#E53935',
        'wep-green':   '#00BFA5',
        'wep-surface': '#F4F7FC',
        'wep-border':  '#E2EAF4',
        'wep-muted':   '#6B7A99',
      },
      fontFamily: {
        sans:    ['Inter', 'system-ui', 'sans-serif'],
        display: ['Syne', 'Inter', 'sans-serif'],
      },
    },
  },
  plugins: [],
}
