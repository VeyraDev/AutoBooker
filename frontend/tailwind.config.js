/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        brand: {
          DEFAULT: "#3B82F6",
          50: "#EFF6FF",
          600: "#2563EB",
          700: "#1D4ED8",
        },
        ink: "#1E293B",
        canvas: "#F8FAFC",
      },
    },
  },
  plugins: [],
};
