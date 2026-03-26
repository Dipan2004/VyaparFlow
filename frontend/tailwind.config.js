/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        bg: '#0A0A0B',
        card: '#121214',
        border: '#272729',
        primary: '#5B7BF5',
        success: '#31C47B',
        warning: '#F5A623',
        destructive: '#D94452',
        text: '#F2F2F2',
        muted: '#7A7A85',
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
      },
      letterSpacing: {
        tighter: '-0.03em',
      },
      animation: {
        'fade-up': 'fadeUp 0.4s ease-out forwards',
        'slide-down': 'slideDown 0.35s ease-out forwards',
        'pulse-glow': 'pulseGlow 2s ease-in-out infinite',
        'typing': 'typing 1.4s ease-in-out infinite',
      },
      keyframes: {
        fadeUp: {
          '0%': { opacity: '0', transform: 'translateY(12px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        slideDown: {
          '0%': { opacity: '0', transform: 'translateY(-20px)' },
          '100%': { opacity: '1', transform: 'translateY(0)' },
        },
        pulseGlow: {
          '0%, 100%': { opacity: '1', boxShadow: '0 0 0 0 currentColor' },
          '50%': { opacity: '0.7', boxShadow: '0 0 8px 2px currentColor' },
        },
        typing: {
          '0%': { opacity: '0.2', transform: 'scale(0.8)' },
          '50%': { opacity: '1', transform: 'scale(1)' },
          '100%': { opacity: '0.2', transform: 'scale(0.8)' },
        },
      },
    },
  },
  plugins: [],
}
