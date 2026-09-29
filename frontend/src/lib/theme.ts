import { useEffect, useState } from "react";
import type { Theme } from "./types";

const STORAGE_KEY = "quantos.theme";

export function resolveTheme(theme: Theme): "light" | "dark" {
  if (theme !== "system") return theme;
  return window.matchMedia?.("(prefers-color-scheme: dark)").matches ? "dark" : "light";
}

export function applyTheme(theme: Theme): void {
  document.documentElement.dataset.theme = resolveTheme(theme);
  try {
    localStorage.setItem(STORAGE_KEY, theme);
  } catch {
    // Storage can be unavailable; the server-side setting still wins on the next load.
  }
}

export function storedTheme(): Theme {
  try {
    const value = localStorage.getItem(STORAGE_KEY);
    if (value === "light" || value === "dark" || value === "system") return value;
  } catch {
    // ignore
  }
  return "system";
}

/** The resolved theme, updating when the OS switches between light and dark. */
export function useResolvedTheme(theme: Theme): "light" | "dark" {
  const [resolved, setResolved] = useState(() => resolveTheme(theme));
  useEffect(() => {
    applyTheme(theme);
    setResolved(resolveTheme(theme));
    if (theme !== "system") return;
    const media = window.matchMedia("(prefers-color-scheme: dark)");
    const onChange = () => {
      applyTheme("system");
      setResolved(resolveTheme("system"));
    };
    media.addEventListener("change", onChange);
    return () => media.removeEventListener("change", onChange);
  }, [theme]);
  return resolved;
}

/** Read a design token (CSS variable) for canvas-based charts. */
export function token(name: string): string {
  return getComputedStyle(document.documentElement).getPropertyValue(name).trim();
}
