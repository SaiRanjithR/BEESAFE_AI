/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        ink: "#111827",
        slate: "#6B7280",
        surface: "#FFFFFF",
        pageBg: "#F3F4F6",
        lineBorder: "#E5E7EB",
        primary: {
          DEFAULT: "#2563EB",
          hover: "#1D4ED8",
        },
        danger: "#DC2626",
        warning: "#D97706",
        success: "#16A34A",
        info: "#0891B2",
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', '-apple-system', 'BlinkMacSystemFont', 'Segoe UI', 'Roboto', 'sans-serif'],
      },
    },
  },
  plugins: [],
};
