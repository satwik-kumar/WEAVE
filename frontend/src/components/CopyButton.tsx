import { useEffect, useRef, useState } from "react";
import { Icon } from "./Icon";

export function CopyButton({
  text,
  label,
  compact = false,
}: {
  text: string;
  label: string;
  compact?: boolean;
}) {
  const [state, setState] = useState<"idle" | "copied" | "unavailable">("idle");
  const timer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);
  const active = useRef(true);
  useEffect(() => {
    active.current = true;
    return () => {
      active.current = false;
      clearTimeout(timer.current);
    };
  }, []);
  const message =
    state === "copied"
      ? "Copied"
      : state === "unavailable"
        ? "Select the text to copy"
        : label;
  return (
    <>
      <button
        className={`copy-button ${compact ? "icon-button" : ""}`}
        type="button"
        aria-label={label}
        title={message}
        onClick={async () => {
          try {
            await navigator.clipboard.writeText(text);
            if (!active.current) return;
            setState("copied");
          } catch {
            if (active.current) setState("unavailable");
          }
          clearTimeout(timer.current);
          if (active.current)
            timer.current = setTimeout(() => setState("idle"), 2000);
        }}
      >
        <Icon name={state === "copied" ? "check" : "copy"} size={14} />
        {!compact && <span>{message}</span>}
      </button>
      <span className="sr-only" role="status">
        {state !== "idle" ? message : ""}
      </span>
    </>
  );
}
