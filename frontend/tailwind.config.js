/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        // ClaimGuard design system (design-system/claimguard/MASTER.md)
        background: "#DBD7D8",
        foreground: "#2B2528",
        primary: { DEFAULT: "#F0225F", hover: "#C11A4C", fg: "#FFFFFF" },
        muted: "#CFC9CB",
        border: "#C4BEC0",
        card: "#FFFFFF",
        // status (data-dense dashboard): green / amber / red
        ok: "#15803D",
        prebreach: "#B45309",
        breach: "#B91C1C",
      },
      fontFamily: {
        sans: ["'Fira Sans'", "system-ui", "sans-serif"],
        mono: ["'Fira Code'", "ui-monospace", "monospace"],
      },
    },
  },
  plugins: [],
};
