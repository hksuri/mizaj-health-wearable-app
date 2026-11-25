"use client";

import { useTheme } from "@/lib/theme";

export function ThemeToggle() {
  const { theme, setTheme } = useTheme();
  return (
    <div
      role="group"
      aria-label="Theme"
      className="flex gap-0.5 rounded-[11px] border border-[var(--m-hair)] bg-[var(--m-chip)] p-[3px]"
    >
      <button
        type="button"
        aria-label="Light mode"
        aria-pressed={theme === "light"}
        onClick={() => setTheme("light")}
        className={`flex h-[30px] w-[34px] items-center justify-center rounded-lg text-sm ${
          theme === "light"
            ? "bg-[var(--m-sel)] text-[var(--m-text)]"
            : "bg-transparent text-[var(--m-faint)]"
        }`}
      >
        L
      </button>
      <button
        type="button"
        aria-label="Dark mode"
        aria-pressed={theme === "dark"}
        onClick={() => setTheme("dark")}
        className={`flex h-[30px] w-[34px] items-center justify-center rounded-lg text-sm ${
          theme === "dark"
            ? "bg-[var(--m-sel)] text-[var(--m-text)]"
            : "bg-transparent text-[var(--m-faint)]"
        }`}
      >
        D
      </button>
    </div>
  );
}
