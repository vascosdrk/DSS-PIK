/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        forest: {
          DEFAULT: '#1b4332',
          light: '#2d6a4f',
          dark: '#081c15',
        }
      }
    },
  },
  corePlugins: {
    preflight: false, // Prevents Tailwind base reset from altering Leaflet maps & existing dashboard styles
  },
  plugins: [],
};

