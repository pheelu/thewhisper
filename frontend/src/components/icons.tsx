/**
 * Set di icone SVG del tema: monocromatiche, stroke = currentColor,
 * così ereditano oro/crema/muted dalla UI (coerenti col glifo ✒︎ del profilo).
 */
import type { SVGProps } from "react";

type IconProps = SVGProps<SVGSVGElement> & { size?: number | string };

function base({ size = "1em", ...props }: IconProps) {
  return {
    width: size,
    height: size,
    viewBox: "0 0 24 24",
    fill: "none",
    stroke: "currentColor",
    strokeWidth: 1.6,
    strokeLinecap: "round" as const,
    strokeLinejoin: "round" as const,
    className: "icon" + (props.className ? ` ${props.className}` : ""),
    ...props,
  };
}

export const IconCrown = (p: IconProps) => (
  <svg {...base(p)}>
    <path d="M4 17h16M5 17l-1.2-8L9 12l3-6 3 6 5.2-3L19 17" />
  </svg>
);

export const IconFeed = (p: IconProps) => (
  <svg {...base(p)}>
    <rect x="3.5" y="4.5" width="17" height="15" rx="2" />
    <path d="M3.5 15.5 9 10l4.5 4.5 3-3 4 4" />
    <circle cx="15.5" cy="8.5" r="1.2" />
  </svg>
);

export const IconCamera = (p: IconProps) => (
  <svg {...base(p)}>
    <path d="M4 8h3l1.5-2.5h7L17 8h3a1 1 0 0 1 1 1v9a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V9a1 1 0 0 1 1-1Z" />
    <circle cx="12" cy="13" r="3.4" />
  </svg>
);

export const IconCameraOff = (p: IconProps) => (
  <svg {...base(p)}>
    <path d="M4 8h3l1.5-2.5h7L17 8h3a1 1 0 0 1 1 1v9a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V9a1 1 0 0 1 1-1Z" />
    <circle cx="12" cy="13" r="3.4" />
    <path d="M4 4l16 16" />
  </svg>
);

export const IconMissive = (p: IconProps) => (
  <svg {...base(p)}>
    <rect x="3" y="5.5" width="18" height="13" rx="1.5" />
    <path d="m3.5 7 8.5 6 8.5-6" />
    <circle cx="12" cy="13" r="1.6" fill="currentColor" stroke="none" />
  </svg>
);

export const IconQuill = (p: IconProps) => (
  <svg {...base(p)}>
    <path d="M20 4c-6 .5-11 3-13.5 8.5C5.2 15.3 5 18 5 20" />
    <path d="M20 4c.5 4.5-1 9.5-5.5 12-1.9 1-4 1.3-6 1" />
    <path d="M9 15c2-.5 4-1.5 6-3.5" />
  </svg>
);

export const IconDice = (p: IconProps) => (
  <svg {...base(p)}>
    <rect x="4" y="4" width="16" height="16" rx="3" />
    <circle cx="8.5" cy="8.5" r="1.1" fill="currentColor" stroke="none" />
    <circle cx="15.5" cy="8.5" r="1.1" fill="currentColor" stroke="none" />
    <circle cx="12" cy="12" r="1.1" fill="currentColor" stroke="none" />
    <circle cx="8.5" cy="15.5" r="1.1" fill="currentColor" stroke="none" />
    <circle cx="15.5" cy="15.5" r="1.1" fill="currentColor" stroke="none" />
  </svg>
);

export const IconMask = (p: IconProps) => (
  <svg {...base(p)}>
    <path d="M3.5 8.5c2.8-1 5.7-1.5 8.5-1.5s5.7.5 8.5 1.5c0 5.5-3 10-8.5 11.5C6.5 18.5 3.5 14 3.5 8.5Z" />
    <path d="M8 12c.8-.7 1.8-.7 2.6 0M13.4 12c.8-.7 1.8-.7 2.6 0" />
    <path d="M9.5 16c1.6 1 3.4 1 5 0" />
  </svg>
);

export const IconComment = (p: IconProps) => (
  <svg {...base(p)}>
    <path d="M20 11.5a7.5 7.5 0 0 1-11 6.6L4 19.5l1.4-4.2A7.5 7.5 0 1 1 20 11.5Z" />
  </svg>
);

export const IconTarget = (p: IconProps) => (
  <svg {...base(p)}>
    <circle cx="12" cy="12" r="8" />
    <circle cx="12" cy="12" r="4.5" />
    <circle cx="12" cy="12" r="1.2" fill="currentColor" stroke="none" />
  </svg>
);

export const IconSparkle = (p: IconProps) => (
  <svg {...base(p)}>
    <path d="M12 3.5c.7 3.8 2.7 5.8 6.5 6.5-3.8.7-5.8 2.7-6.5 6.5-.7-3.8-2.7-5.8-6.5-6.5 3.8-.7 5.8-2.7 6.5-6.5Z" />
    <path d="M18.5 15.5c.3 1.7 1.2 2.6 3 3-1.8.3-2.7 1.2-3 3-.3-1.8-1.2-2.7-3-3 1.8-.4 2.7-1.3 3-3Z" />
  </svg>
);

export const IconTrash = (p: IconProps) => (
  <svg {...base(p)}>
    <path d="M4.5 6.5h15M9.5 6.5v-2h5v2M6.5 6.5 7.5 20h9l1-13.5" />
    <path d="M10 10.5v6M14 10.5v6" />
  </svg>
);

export const IconSend = (p: IconProps) => (
  <svg {...base(p)}>
    <path d="M4 12 20 4l-4.5 16-4-6.5L4 12Z" />
    <path d="m11.5 13.5 4-4" />
  </svg>
);

export const IconCandle = (p: IconProps) => (
  <svg {...base(p)}>
    <path d="M12 3c-1.3 1.6-2 2.7-2 3.8A2 2 0 0 0 14 7c0-1.2-.7-2.4-2-4Z" />
    <path d="M9.5 10.5h5V20h-5zM7 20h10" />
  </svg>
);

export const IconTrophy = (p: IconProps) => (
  <svg {...base(p)}>
    <path d="M8 4h8v5a4 4 0 0 1-8 0V4Z" />
    <path d="M8 5H5a3 3 0 0 0 3 4M16 5h3a3 3 0 0 1-3 4" />
    <path d="M12 13v3M9 19h6M10 16h4v3h-4z" />
  </svg>
);

export const IconEye = (p: IconProps) => (
  <svg {...base(p)}>
    <path d="M3 12s3.5-6 9-6 9 6 9 6-3.5 6-9 6-9-6-9-6Z" />
    <circle cx="12" cy="12" r="2.6" />
  </svg>
);
