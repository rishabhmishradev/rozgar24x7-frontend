/** @type {import('tailwindcss').Config} */
export default {
  darkMode: "class",
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        // Corporate Modern palette — maps to CSS custom properties
        accent:     "var(--color-accent)",
        secondary:  "var(--color-secondary)",
        "bg-base":  "var(--color-bg)",
        "bg-section":"var(--color-bg-section)",
        heading:    "var(--color-heading)",
        body:       "var(--color-body)",
        muted:      "var(--color-muted)",
        border:     "var(--color-border)",
      },
      fontFamily: {
        display: ['"Inter"', 'sans-serif'],
        sans:    ['Outfit', 'sans-serif'],
      },
      animation: {
        'marquee-lr': 'marquee-lr 35s linear infinite',
      },
      keyframes: {
        'marquee-lr': {
          '0%':   { transform: 'translateX(-50%)' },
          '100%': { transform: 'translateX(0)' },
        }
      }
    },
  },
  plugins: [],
};