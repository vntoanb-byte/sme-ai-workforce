import type { Config } from 'tailwindcss'

export default {
  content: ['./index.html', './src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      fontFamily: {
        sans: ['Inter', 'Segoe UI', 'Noto Sans', 'system-ui', 'sans-serif'],
        mono: ['Consolas', 'DejaVu Sans Mono', 'monospace'],
      },
      colors: {
        ink:  { DEFAULT: '#16233C', soft: '#54637C', mute: '#7E8CA3', faint: '#9AA6B8' },
        line: { DEFAULT: '#E2E8F1', soft: '#F1F5FA' },
        nav:  { DEFAULT: '#1B2A47', hover: '#2E4576', text: '#B7C4D8', line: '#2C3E60' },
        brand:{ DEFAULT: '#2E5BD8', dark: '#1E43AC', light: '#EEF3FF' },
      },
    },
  },
  plugins: [],
} satisfies Config
