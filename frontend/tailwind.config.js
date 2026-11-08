/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      fontFamily: { sans: ["Inter", "system-ui", "-apple-system", "Segoe UI", "sans-serif"], display: ["var(--font-display)", "Oswald", "system-ui", "sans-serif"] },
      colors: { brand: "var(--c-primary)", brand2: "var(--c-secondary)", accent: "var(--c-accent)", ink: "var(--c-ink)", muted: "var(--c-muted)", surface: "var(--c-surface)", page: "var(--c-bg)", line: "var(--c-border)" },
      boxShadow: { card: "0 1px 2px rgba(15,23,42,.06), 0 8px 24px -12px rgba(15,23,42,.18)", glow: "0 0 0 1px var(--c-border), 0 18px 50px -20px var(--c-primary)" },
      keyframes: { floaty: { "0%,100%": { transform: "translateY(0)" }, "50%": { transform: "translateY(-8px)" } }, shimmer: { "100%": { transform: "translateX(100%)" } } },
      animation: { floaty: "floaty 6s ease-in-out infinite" },
    },
  },
  plugins: [],
};
