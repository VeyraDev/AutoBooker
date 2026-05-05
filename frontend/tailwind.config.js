/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        brand: {
          50: "#EFF3FF",
          100: "#DFE8FF",
          200: "#C5D5FF",
          300: "#9FB8FF",
          400: "#7899F8",
          500: "#3563E9",
          600: "#2F57CC",
          700: "#284AAE",
          800: "#213D90",
          900: "#1A3172",
          DEFAULT: "#3563E9",
        },
        ink: "#1E293B",
        canvas: "#F8FAFC",
      },
    },
  },
  plugins: [],
};
