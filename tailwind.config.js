// tailwind/tailwind.config.js
module.exports = {
  content: [
    "./inventory/templates/**/*.html",
    "./inventory/**/*.py",
    "./templates/**/*.html",
  ],
  theme: {
    extend: {
      colors: {
        brand: {
          50:  "#ECFDFE",
          100: "#CCFBFE",
          200: "#A5F3FC",
          300: "#67E8F9",
          400: "#22D3EE",
          500: "#06B6D4",
          600: "#0891B2",
          700: "#0E7490",
          800: "#155E75",
          900: "#164E63",
        },
        neutral: {
          50:  "#F8FAFC",
          100: "#F1F5F9",
          200: "#E2E8F0",
          300: "#CBD5E1",
          400: "#94A3B8",
          500: "#64748B",
          600: "#475569",
          700: "#334155",
          800: "#1E293B",
          900: "#0F172A",
        },
        success: {
          500: "#10B981",
          600: "#059669",
          700: "#047857",
        },
        warning: {
          500: "#F59E0B",
          600: "#D97706",
        },
        danger: {
          500: "#EF4444",
          600: "#DC2626",
        },
      },
      fontFamily: {
        sans: ["Inter", "system-ui", "sans-serif"],
      },
      borderRadius: {
        xl: "1rem",
      },
      boxShadow: {
        soft: "0 8px 20px -10px rgba(6,182,212,0.25)",
      },
    },
  },
  plugins: [],
};
