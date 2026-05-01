/** @type {import('tailwindcss').Config} */
export default {
  darkMode: "class", // 🔥 ye line important hai
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      animation: {
        'marquee-lr': 'marquee-lr 35s linear infinite',
      },
      keyframes: {
        'marquee-lr': {
          '0%': { transform: 'translateX(-50%)' },
          '100%': { transform: 'translateX(0)' },
        }
      }
    },
  },
  plugins: [],
};