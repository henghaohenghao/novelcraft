/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    "./app/**/*.{js,ts,jsx,tsx,mdx}",
    "./components/**/*.{js,ts,jsx,tsx,mdx}",
  ],
  theme: {
    extend: {
      colors: {
        'claude-cream': '#F5F5F0',
        'claude-beige': '#E8E6E1',
        'claude-brown': '#6B5B4F',
        'claude-dark': '#2A2420',
        'claude-accent': '#CC9966',
        'claude-border': '#D4D1CC',
      },
      fontFamily: {
        sans: ['-apple-system', 'BlinkMacSystemFont', 'Segoe UI', 'Roboto', 'Inter', 'system-ui', 'sans-serif'],
      },
    },
  },
  plugins: [],
};