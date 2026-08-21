/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
      },
      colors: {
        primary: {
          50:  '#eef2ff',
          100: '#e0e7ff',
          200: '#c7d2fe',
          300: '#a5b4fc',
          400: '#818cf8',
          500: '#6366f1',
          600: '#4f46e5',
          700: '#4338ca',
          800: '#3730a3',
          900: '#312e81',
        },
        accent: {
          DEFAULT: '#06b6d4',
          dark:    '#0891b2',
        },
        surface: {
          DEFAULT: '#0f172a',
          card:    '#1e293b',
          border:  '#334155',
          muted:   '#475569',
        },
      },
      backgroundImage: {
        'gradient-radial': 'radial-gradient(var(--tw-gradient-stops))',
        'hero-glow': 'radial-gradient(ellipse 80% 60% at 50% -10%, rgba(99,102,241,0.35) 0%, transparent 70%)',
      },
      animation: {
        'spin-slow':       'spin 3s linear infinite',
        'pulse-slow':      'pulse 3s cubic-bezier(0.4, 0, 0.6, 1) infinite',
        'fade-in':         'fadeIn 0.5s ease-out',
        'slide-up':        'slideUp 0.4s ease-out',
        'score-ring':      'scoreRing 1.2s ease-out forwards',
        'shimmer':         'shimmer 1.5s infinite',
        'float':           'floatBubble 4s ease-in-out infinite',
        'pulse-glow':      'pulseGlow 2s ease-in-out infinite',
        'slide-in-right':  'slideInRight 0.3s ease-out',
        'count-up':        'countUp 0.5s ease-out both',
      },
      keyframes: {
        fadeIn:      { from: { opacity: '0' }, to: { opacity: '1' } },
        slideUp:     { from: { opacity: '0', transform: 'translateY(16px)' }, to: { opacity: '1', transform: 'translateY(0)' } },
        scoreRing:   { from: { 'stroke-dashoffset': '440' }, to: { 'stroke-dashoffset': 'var(--dash-offset)' } },
        shimmer:     { '0%': { 'background-position': '-400% 0' }, '100%': { 'background-position': '400% 0' } },
        floatBubble: { '0%, 100%': { transform: 'translateY(0px)' }, '50%': { transform: 'translateY(-12px)' } },
        pulseGlow:   { '0%, 100%': { 'box-shadow': '0 0 0 0 rgba(99,102,241,0.4)' }, '50%': { 'box-shadow': '0 0 0 8px rgba(99,102,241,0)' } },
        slideInRight:{ from: { opacity: '0', transform: 'translateX(32px)' }, to: { opacity: '1', transform: 'translateX(0)' } },
        countUp:     { from: { opacity: '0', transform: 'translateY(8px)' }, to: { opacity: '1', transform: 'translateY(0)' } },
      },
    },
  },
  plugins: [],
}
