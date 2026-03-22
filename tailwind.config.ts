import type { Config } from "tailwindcss";

const config: Config = {
  darkMode: ["class", '[data-theme-type="dark"]'],
  content: [
    "./index.html",
    "./src/**/*.{ts,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        bg: {
          primary:   "var(--color-bg-primary)",
          secondary: "var(--color-bg-secondary)",
          tertiary:  "var(--color-bg-tertiary)",
          sidebar:   "var(--color-bg-sidebar)",
          input:     "var(--color-bg-input)",
          hover:     "var(--color-bg-hover)",
          selection: "var(--color-bg-selection)",
        },
        text: {
          primary:   "var(--color-text-primary)",
          secondary: "var(--color-text-secondary)",
          muted:     "var(--color-text-muted)",
          disabled:  "var(--color-text-disabled)",
        },
        accent: {
          DEFAULT: "var(--color-accent-primary)",
          hover:   "var(--color-accent-hover)",
          muted:   "var(--color-accent-muted)",
        },
        border: {
          DEFAULT: "var(--color-border-default)",
          focus:   "var(--color-border-focus)",
        },
        status: {
          error:   "var(--color-status-error)",
          warning: "var(--color-status-warning)",
          success: "var(--color-status-success)",
          info:    "var(--color-status-info)",
        },
      },
      fontFamily: {
        sans: [
          "-apple-system",
          "BlinkMacSystemFont",
          '"Segoe UI"',
          "Roboto",
          "sans-serif",
        ],
        mono: [
          '"JetBrains Mono"',
          '"Fira Code"',
          "Menlo",
          "Monaco",
          "Consolas",
          "monospace",
        ],
      },
      borderRadius: {
        sm: "4px",
        md: "6px",
        lg: "8px",
      },
    },
  },
  plugins: [],
};

export default config;
