/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: ['"Inter"', "system-ui", "sans-serif"],
        mono: ['"JetBrains Mono"', "ui-monospace", "monospace"],
      },
      colors: {
        sovereign: {
          50: "#eef7ff",
          100: "#d9ecff",
          200: "#bcdfff",
          300: "#8eccff",
          400: "#59afff",
          500: "#338dfc",
          600: "#1d6ef1",
          700: "#1558de",
          800: "#1847b4",
          900: "#1a3f8e",
          950: "#152856",
        },
      },
    },
  },
  plugins: [],
};
