/** @type {import('tailwindcss').Config} */
module.exports = {
  darkMode: ['class'],
  content: [
    './src/renderer/src/**/*.{js,ts,jsx,tsx}',
    './src/renderer/index.html',
    './node_modules/streamdown/dist/*.js'
  ],
  theme: {
    extend: {
      colors: {
        border: 'hsl(var(--border))',
        input: 'hsl(var(--input))',
        ring: 'hsl(var(--ring))',
        background: 'hsl(var(--background))',
        foreground: 'hsl(var(--foreground))',
        primary: {
          DEFAULT: 'hsl(var(--primary))',
          foreground: 'hsl(var(--primary-foreground))'
        },
        secondary: {
          DEFAULT: 'hsl(var(--secondary))',
          foreground: 'hsl(var(--secondary-foreground))'
        },
        destructive: {
          DEFAULT: 'hsl(var(--destructive))',
          foreground: 'hsl(var(--destructive-foreground))'
        },
        muted: {
          DEFAULT: 'hsl(var(--muted))',
          foreground: 'hsl(var(--muted-foreground))'
        },
        accent: {
          DEFAULT: 'hsl(var(--accent))',
          foreground: 'hsl(var(--accent-foreground))'
        },
        popover: {
          DEFAULT: 'hsl(var(--popover))',
          foreground: 'hsl(var(--popover-foreground))'
        },
        card: {
          DEFAULT: 'hsl(var(--card))',
          foreground: 'hsl(var(--card-foreground))'
        },
        // Forest Green color palette
        forest: {
          50: '#f0f5f3',
          100: '#d9e8e2',
          200: '#b6d1c7',
          300: '#8bb5a6',
          400: '#639583',
          500: '#2D5A45',
          600: '#274e3c',
          700: '#214133',
          800: '#1b352a',
          900: '#162b23'
        },
        // Warm neutral palette
        warm: {
          50: '#FAF9F6',
          100: '#F5F4F1',
          200: '#EEEDEA',
          300: '#E0DFDC',
          400: '#B8B7B4',
          500: '#4A4A4A',
          600: '#3A3A3A',
          700: '#2A2A2A',
          800: '#1A1A1A',
          900: '#0A0A0A'
        },
        // Amber accent
        amber: {
          DEFAULT: '#E69500',
          light: '#FFB84D',
          dark: '#CC8400'
        }
      },
      borderRadius: {
        lg: 'var(--radius)',
        md: 'calc(var(--radius) - 2px)',
        sm: 'calc(var(--radius) - 4px)'
      },
      boxShadow: {
        warm: '0 4px 24px rgba(0, 0, 0, 0.06)',
        'warm-sm': '0 2px 12px rgba(0, 0, 0, 0.04)',
        'warm-lg': '0 8px 32px rgba(0, 0, 0, 0.08)',
        glass: '0 4px 24px rgba(45, 90, 69, 0.08)'
      },
      backdropBlur: {
        glass: '12px'
      },
      keyframes: {
        'accordion-down': {
          from: { height: '0' },
          to: { height: 'var(--radix-accordion-content-height)' }
        },
        'accordion-up': {
          from: { height: 'var(--radix-accordion-content-height)' },
          to: { height: '0' }
        }
      },
      animation: {
        'accordion-down': 'accordion-down 0.2s ease-out',
        'accordion-up': 'accordion-up 0.2s ease-out'
      }
    }
  },
  plugins: [require('@tailwindcss/typography')]
}
