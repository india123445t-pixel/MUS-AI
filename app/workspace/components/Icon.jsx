import React from 'react';

// Single consistent icon set — 1.6 stroke, 24 viewBox, rendered at 18px default.
// Directional icons (send, chevron) are mirrored in RTL via CSS [dir=rtl] .ic-flip.
const P = {
  chat: 'M21 12a8 8 0 0 1-8 8H5l-2 2V12a8 8 0 0 1 8-8h2a8 8 0 0 1 8 8z',
  work: 'M4 7h16v13H4zM8 7V5a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2M4 12h16',
  code: 'm8 8-4 4 4 4M16 8l4 4-4 4M13 5l-2 14',
  folder: 'M3 6a2 2 0 0 1 2-2h4l2 2h8a2 2 0 0 1 2 2v10a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z',
  library: 'M4 4h4v16H4zM10 4h4v16h-4zM17.5 4.5 21 19l-3.8 1L14 5.6z',
  clock: 'M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18zM12 7v5l3 3',
  puzzle: 'M9 4a2 2 0 1 1 4 0h4v4a2 2 0 1 1 0 4v4h-4a2 2 0 1 0-4 0H5v-4a2 2 0 1 0 0-4V4z',
  gear: 'M12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6zM19 12a7 7 0 0 0-.1-1.2l2-1.5-2-3.5-2.4 1a7 7 0 0 0-2-1.2L14 3h-4l-.4 2.6a7 7 0 0 0-2 1.2l-2.5-1-2 3.5 2.1 1.5a7 7 0 0 0 0 2.4L3 14.7l2 3.5 2.4-1a7 7 0 0 0 2 1.2L10 21h4l.4-2.6a7 7 0 0 0 2-1.2l2.5 1 2-3.5-2.1-1.5c.1-.4.1-.8.1-1.2z',
  search: 'M11 19a8 8 0 1 0 0-16 8 8 0 0 0 0 16zM21 21l-4.3-4.3',
  plus: 'M12 5v14M5 12h14',
  send: 'M5 12h14M13 6l6 6-6 6',
  stop: 'M7 7h10v10H7z',
  mic: 'M12 15a3 3 0 0 0 3-3V6a3 3 0 1 0-6 0v6a3 3 0 0 0 3 3zM19 11a7 7 0 0 1-14 0M12 18v3',
  globe: 'M12 21a9 9 0 1 0 0-18 9 9 0 0 0 0 18zM3 12h18M12 3c2.5 2.6 4 5.7 4 9s-1.5 6.4-4 9c-2.5-2.6-4-5.7-4-9s1.5-6.4 4-9z',
  flask: 'M10 3v6L4.6 18a2 2 0 0 0 1.8 3h11.2a2 2 0 0 0 1.8-3L14 9V3M8 3h8M7 15h10',
  clip: 'M21 12.5 12.7 20.8a5 5 0 0 1-7-7l8.4-8.5a3.3 3.3 0 1 1 4.7 4.7L10.4 18.4a1.7 1.7 0 0 1-2.4-2.4l7.8-7.8',
  dots: 'M12 13a1 1 0 1 0 0-2 1 1 0 0 0 0 2zM19 13a1 1 0 1 0 0-2 1 1 0 0 0 0 2zM5 13a1 1 0 1 0 0-2 1 1 0 0 0 0 2z',
  pin: 'M12 3l4 4-1 1 1.5 4L13 15l-1 6-1-6-3.5-3L9 8 8 7z',
  pencil: 'M17 3l4 4L8 20H4v-4z',
  trash: 'M4 7h16M9 7V4h6v3M6 7l1 13h10l1-13M10 11v5M14 11v5',
  check: 'M4 12l5 5L20 6',
  x: 'M6 6l12 12M18 6 6 18',
  chevD: 'm6 9 6 6 6-6',
  chevR: 'm9 6 6 6-6 6',
  external: 'M14 4h6v6M20 4l-9 9M20 14v6H4V4h6',
  download: 'M12 3v12M6 11l6 6 6-6M4 21h16',
  play: 'M7 5l12 7-12 7z',
  pause: 'M7 5h4v14H7zM13 5h4v14h-4z',
  warn: 'M12 3 1.5 21h21zM12 9v5M12 17.5v.5',
  spark: 'M12 2l2.2 6.6L21 11l-6.8 2.4L12 20l-2.2-6.6L3 11l6.8-2.4z',
  copy: 'M9 9h11v11H9zM5 15H4V4h11v1',
  branch: 'M6 3v12M6 21v-2M18 9a3 3 0 1 0 0-6 3 3 0 0 0 0 6zM18 9a9 9 0 0 1-9 9M6 21a2 2 0 1 0 0-4 2 2 0 0 0 0 4zM6 15a2 2 0 1 0 0-4',
  volume: 'M11 5 6 9H3v6h3l5 4zM15 9a4 4 0 0 1 0 6M18 6.5a8 8 0 0 1 0 11',
  thumbUp: 'M7 11v9H4v-9zM7 11l4-7a2 2 0 0 1 3.5 1.8L13.5 10H19a2 2 0 0 1 2 2.3l-1.2 6A2 2 0 0 1 17.8 20H7',
  thumbDown: 'M7 13V4H4v9zM7 13l4 7a2 2 0 0 0 3.5-1.8L13.5 14H19a2 2 0 0 0 2-2.3l-1.2-6A2 2 0 0 0 17.8 4H7',
  retry: 'M3 12a9 9 0 1 0 3-6.7M3 4v5h5',
  file: 'M6 2h8l4 4v16H6zM14 2v4h4',
  image: 'M4 4h16v16H4zM4 15l4-4 4 4 3-3 5 5M9 9.5a.5.5 0 1 0 0-1 .5.5 0 0 0 0 1z',
  menu: 'M4 6h16M4 12h16M4 18h16',
  terminal: 'm5 7 5 5-5 5M12 17h7',
  history: 'M3 12a9 9 0 1 0 3-6.7M3 4v5h5M12 7v5l3 3',
  git: 'M6 6a2 2 0 1 0 0-4 2 2 0 0 0 0 4zM6 22a2 2 0 1 0 0-4 2 2 0 0 0 0 4zM18 12a2 2 0 1 0 0-4 2 2 0 0 0 0 4zM6 6v12M18 12h-6a4 4 0 0 1-4-4',
  user: 'M12 11a4 4 0 1 0 0-8 4 4 0 0 0 0 8zM4 21a8 8 0 0 1 16 0'
};

export default function Icon({ name, size = 18, className = '', flip = false }) {
  const d = P[name];
  if (!d) return null;
  return (
    <svg
      className={'ic-svg' + (flip ? ' ic-flip' : '') + (className ? ' ' + className : '')}
      width={size} height={size} viewBox="0 0 24 24" fill="none"
      stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round"
      aria-hidden="true">
      <path d={d} />
    </svg>
  );
}
