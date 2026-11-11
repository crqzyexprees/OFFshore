import { useState } from "react";

export type ThemePreference = "system" | "light" | "dark";

const STORAGE_KEY = "finance.theme";
const systemDark = window.matchMedia("(prefers-color-scheme: dark)");

// The choice is a per-device convenience, so localStorage is enough; it may be
// unavailable, in which case the app just follows the system.
export function getThemePreference(): ThemePreference {
  try {
    const value = localStorage.getItem(STORAGE_KEY);
    return value === "light" || value === "dark" ? value : "system";
  } catch {
    return "system";
  }
}

function apply(preference: ThemePreference) {
  const dark = preference === "dark" || (preference === "system" && systemDark.matches);
  document.documentElement.classList.toggle("dark", dark);
}

export const applyTheme = () => apply(getThemePreference());

systemDark.addEventListener("change", applyTheme);

export function useThemePreference(): [ThemePreference, (p: ThemePreference) => void] {
  const [preference, setPreference] = useState(getThemePreference);
  const set = (next: ThemePreference) => {
    try {
      if (next === "system") localStorage.removeItem(STORAGE_KEY);
      else localStorage.setItem(STORAGE_KEY, next);
    } catch {
      // Not persisted; still applied for this session below.
    }
    setPreference(next);
    apply(next);
  };
  return [preference, set];
}
