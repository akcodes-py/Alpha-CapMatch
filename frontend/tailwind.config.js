/** @type {import('tailwindcss').Config} */
export default {
  corePlugins: {
    preflight: false,
  },
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  theme: {
    extend: {
      colors: {
        pageBg: "#f4f5f7",
        textMain: "#1c1e21",
        cardBorder: "#e2e4e9",
        btnBorder: "#c9ccd3",
        btnHover: "#f0f1f4",
      },
    },
  },
  plugins: [],
};
