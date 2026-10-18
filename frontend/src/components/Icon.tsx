import type { CSSProperties } from "react";

const paths: Record<string, string> = {
  sun: "M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8ZM12 2v2m0 16v2M2 12h2m16 0h2M5 5l1.5 1.5m11 11L19 19M5 19l1.5-1.5m11-11L19 5",
  brain: "M8 4 4 8v8l4 4h8l4-4V8l-4-4H8Zm0 0v16M16 4v16M4 12h16M8 8h8M8 16h8",
  chat: "M5 4h14a2 2 0 0 1 2 2v10a2 2 0 0 1-2 2H9l-6 3V6a2 2 0 0 1 2-2Zm2 5h10M7 13h6",
  graph:
    "M9 5a3 3 0 1 1-6 0 3 3 0 0 1 6 0Zm12 14a3 3 0 1 1-6 0 3 3 0 0 1 6 0ZM9 19a3 3 0 1 1-6 0 3 3 0 0 1 6 0ZM6 8v8m2-9 8 10M9 19h6",
  health: "M3 12h4l3-8 4 16 3-8h4",
  book: "M12 5C9 3 5 3 3 4v15c3-1 6-1 9 1m0-15c3-2 7-2 9-1v15c-3-1-6-1-9 1V5Z",
  arrow: "M5 12h14m-6-6 6 6-6 6",
  service: "M4 3h16v7H4V3Zm0 11h16v7H4v-7ZM7 6h.01M7 17h.01M11 6h6m-6 11h6",
  team: "M8 10a3 3 0 1 0 0-6 3 3 0 0 0 0 6Zm8 0a3 3 0 1 0 0-6M2 20v-3a5 5 0 0 1 10 0v3m3-7a5 5 0 0 1 5 5v2",
  person: "M16 7a4 4 0 1 1-8 0 4 4 0 0 1 8 0ZM4 21v-3a8 8 0 0 1 16 0v3",
  decision: "M12 3v5m0 0-7 5v7m7-12 7 5v7M2 17l3 3 3-3m8 0 3 3 3-3",
  incident: "m12 3 10 18H2L12 3Zm0 6v5m0 3h.01",
  repository: "M5 3h14v18H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2Zm0 14h14M8 6h7",
  document: "M5 3h10l4 4v14H5V3Zm10 0v5h4M8 12h8m-8 4h6",
  file: "m8 8-4 4 4 4m8-8 4 4-4 4m-3-12-2 16",
  ticket: "M3 5h18v5a2 2 0 0 0 0 4v5H3v-5a2 2 0 0 0 0-4V5Zm12 0v14",
  project: "M3 7h7l2-3h9v16H3V7Z",
  test: "m9 3 0 6-6 11h18L15 9V3M7 3h10M7 15h10",
  fit: "M8 3H3v5m13-5h5v5M3 16v5h5m13-5v5h-5",
  plus: "M12 5v14M5 12h14",
  minus: "M5 12h14",
  layers: "m12 3 10 6-10 6L2 9l10-6Zm-10 10 10 6 10-6M2 17l10 6 10-6",
};

export function Icon({
  name,
  size = 18,
  style,
}: {
  name: string;
  size?: number;
  style?: CSSProperties;
}) {
  return (
    <svg
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.6"
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      style={style}
    >
      <path d={paths[name] ?? paths.graph} />
    </svg>
  );
}
