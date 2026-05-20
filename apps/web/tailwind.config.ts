import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        obsidian: "#070807",
        graphite: "#101311",
        graphite2: "#171b18",
        panel: "#111612",
        panel2: "#151a17",
        line: "#28322c",
        muted: "#9aa39a",
        ink: "#eef4ec",
        accent: "#67e8b9",
        amber: "#f3c969",
        signal: "#8cc8ff",
        rose: "#f08aa3"
      },
      fontFamily: {
        sans: ["Inter", "ui-sans-serif", "system-ui", "sans-serif"],
        mono: ["JetBrains Mono", "SFMono-Regular", "Menlo", "monospace"]
      }
    }
  },
  plugins: []
};

export default config;
