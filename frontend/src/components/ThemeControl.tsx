import { useEffect, useState } from "react";
import { Icon } from "./Icon";

type Preference = "light" | "dark" | "system";
const valid = (value: string | null | undefined): Preference =>
  value === "light" || value === "dark" ? value : "system";

export function ThemeControl() {
  const [preference, setPreference] = useState<Preference>(() =>
    valid(document.documentElement.dataset.preference),
  );
  useEffect(() => {
    const query = window.matchMedia("(prefers-color-scheme: dark)");
    const apply = () => {
      document.documentElement.dataset.preference = preference;
      document.documentElement.dataset.theme =
        preference === "system"
          ? query.matches
            ? "dark"
            : "light"
          : preference;
    };
    apply();
    query.addEventListener("change", apply);
    const sync = (event: StorageEvent) => {
      if (event.key === "weave-theme" || event.key === null)
        setPreference(valid(event.newValue));
    };
    window.addEventListener("storage", sync);
    return () => {
      query.removeEventListener("change", apply);
      window.removeEventListener("storage", sync);
    };
  }, [preference]);
  return (
    <label className="theme-control">
      <Icon name="sun" size={16} />
      <span>Theme</span>
      <select
        aria-label="Color theme"
        value={preference}
        onChange={(event) => {
          const next = valid(event.target.value);
          // Apply before React's effect and persist independently of storage access.
          document.documentElement.dataset.preference = next;
          document.documentElement.dataset.theme =
            next === "system"
              ? matchMedia("(prefers-color-scheme: dark)").matches
                ? "dark"
                : "light"
              : next;
          setPreference(next);
          try {
            localStorage.setItem("weave-theme", next);
          } catch {
            /* Session theme still works. */
          }
        }}
      >
        <option value="system">System</option>
        <option value="light">Light</option>
        <option value="dark">Dark</option>
      </select>
    </label>
  );
}
