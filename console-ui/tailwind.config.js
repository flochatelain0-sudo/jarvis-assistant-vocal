/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        bg: '#050505',
        panel: '#0c0c0c',
        'panel-light': '#111111',
        'panel-up': '#151515',
        orange: '#FF6A00',
        'orange-bright': '#FF8500',
        green: '#20E878',
        textc: '#F5F5F5',
        muted: '#777777',
        dim: '#C7C7C7',
        bord: 'rgba(255,255,255,0.08)',
        'bord-orange': 'rgba(255,110,0,0.25)',
      },
      fontFamily: {
        mono: ['"SF Mono"', '"JetBrains Mono"', 'Menlo', 'Consolas', 'monospace'],
        sans: ['-apple-system', 'BlinkMacSystemFont', '"Segoe UI"', 'Roboto', 'Helvetica', 'Arial', 'sans-serif'],
      },
    },
  },
  plugins: [],
}
