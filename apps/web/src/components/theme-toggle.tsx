"use client";
import { useEffect, useSyncExternalStore } from "react";
import { Moon, Sun } from "lucide-react";
const key = "aegisgraph-theme";
const eventName = "aegisgraph-theme-changed";
function readTheme(): "dark" | "light" {
  try {
    const saved = localStorage.getItem(key);
    if (saved === "light" || saved === "dark") return saved;
  } catch {
    /* Theme still works when browser storage is unavailable. */
  }
  return document.documentElement.dataset.theme === "light" ? "light" : "dark";
}
function subscribe(listener: () => void) {
  window.addEventListener(eventName, listener);
  window.addEventListener("storage", listener);
  return () => {
    window.removeEventListener(eventName, listener);
    window.removeEventListener("storage", listener);
  };
}
export function ThemeToggle() {
  const theme = useSyncExternalStore(subscribe, readTheme, () => "dark");
  useEffect(() => {
    document.documentElement.dataset.theme = theme;
  }, [theme]);
  function toggle() {
    const next = theme === "dark" ? "light" : "dark";
    document.documentElement.dataset.theme = next;
    try {
      localStorage.setItem(key, next);
    } catch {
      /* Storage is optional. */
    }
    window.dispatchEvent(new Event(eventName));
  }
  return (
    <button
      className="theme-toggle"
      onClick={toggle}
      aria-label={`Switch to ${theme === "dark" ? "light" : "dark"} theme`}
      title={`Switch to ${theme === "dark" ? "light" : "dark"} theme`}
    >
      {theme === "dark" ? <Sun size={16} /> : <Moon size={16} />}
      <span>{theme === "dark" ? "Light" : "Dark"}</span>
    </button>
  );
}
