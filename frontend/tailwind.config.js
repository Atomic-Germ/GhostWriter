/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        ink: {
          50: "#f7f6f3",
          100: "#ebe8e0",
          200: "#d6d0c2",
          300: "#b8ae9a",
          400: "#9a8c74",
          500: "#7f725c",
          600: "#665b4a",
          700: "#50483c",
          800: "#3a342c",
          900: "#24201b",
          950: "#16140f",
        },
        accent: {
          DEFAULT: "#c4a35a",
          dim: "#a88b45",
          glow: "#e8d5a3",
        },
        panel: {
          DEFAULT: "#1c1915",
          raised: "#252119",
          border: "#3a342c",
        },
      },
      fontFamily: {
        serif: ['"Literata"', "Georgia", "Cambria", "serif"],
        sans: ['"DM Sans"', "system-ui", "sans-serif"],
        mono: ['"IBM Plex Mono"', "ui-monospace", "monospace"],
      },
      boxShadow: {
        soft: "0 8px 30px rgba(0,0,0,0.35)",
      },
    },
  },
  plugins: [],
};
