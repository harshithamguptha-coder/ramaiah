/** Inline SVG icon set. Small, dependency-free, stroke-based. */

const paths = {
  dashboard: 'M3 3h7v7H3zM14 3h7v5h-7zM14 12h7v9h-7zM3 14h7v7H3z',
  upload: 'M12 16V4m0 0L8 8m4-4 4 4M4 17v2a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-2',
  analysis: 'M9 3h6M10 3v6.5L5.2 17A2 2 0 0 0 7 20h10a2 2 0 0 0 1.8-3L14 9.5V3M8 14h8',
  classical: 'M4 19V9m5 10V5m5 14v-7m5 7V8',
  quantum: 'M12 2a10 10 0 1 0 0 20 10 10 0 0 0 0-20zm0 4.5a5.5 5.5 0 1 1 0 11 5.5 5.5 0 0 1 0-11zM12 2v20M2 12h20',
  comparison: 'M12 3v18M7 8L3 12l4 4M17 8l4 4-4 4M7 8h10M7 16h10',
  recommendation: 'm9 12 2 2 4-4m6 2a9 9 0 1 1-18 0 9 9 0 0 1 18 0z',
  report: 'M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8zm0 0v6h6M9 13h6M9 17h6',
  file: 'M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8zm0 0v6h6',
  database: 'M12 8c4.4 0 8-1.3 8-3s-3.6-3-8-3-8 1.3-8 3 3.6 3 8 3zM4 5v14c0 1.7 3.6 3 8 3s8-1.3 8-3V5M4 12c0 1.7 3.6 3 8 3s8-1.3 8-3',
  clock: 'M12 8v4l3 2m6-2a9 9 0 1 1-18 0 9 9 0 0 1 18 0z',
  close: 'M6 6l12 12M18 6 6 18',
  check: 'm5 13 4 4L19 7',
  download: 'M12 3v12m0 0 4-4m-4 4-4-4M4 17v2a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2v-2',
  warning: 'M12 9v4m0 4h.01M10.3 3.9 1.8 18a2 2 0 0 0 1.7 3h17a2 2 0 0 0 1.7-3L13.7 3.9a2 2 0 0 0-3.4 0z',
  info: 'M12 16v-4m0-4h.01M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0z',
  search: 'M21 21l-4.3-4.3M17 11a6 6 0 1 1-12 0 6 6 0 0 1 12 0z',
  menu: 'M3 6h18M3 12h18M3 18h18',
  plus: 'M12 5v14M5 12h14',
  trash: 'M3 6h18M8 6V4h8v2m1 0v14a2 2 0 0 1-2 2H9a2 2 0 0 1-2-2V6',
  arrowRight: 'M5 12h14m0 0-6-6m6 6-6 6',
  layers: 'm12 2 9 5-9 5-9-5 9-5zM3 12l9 5 9-5M3 17l9 5 9-5',
  cpu: 'M6 6h12v12H6zM9 2v4M15 2v4M9 18v4M15 18v4M2 9h4M2 15h4M18 9h4M18 15h4',
}

export default function Icon({ name, size = 18, className = '', strokeWidth = 1.7, ...rest }) {
  const d = paths[name] || paths.info
  return (
    <svg
      className={className}
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={strokeWidth}
      strokeLinecap="round"
      strokeLinejoin="round"
      aria-hidden="true"
      focusable="false"
      {...rest}
    >
      <path d={d} />
    </svg>
  )
}

export const ICON_NAMES = Object.keys(paths)
