import React from 'react';

interface CenterBarProps extends React.SVGProps<SVGSVGElement> {}

/** UI-16: widevane "center" — a plain bold keyboard-pipe bar, per the owner's
 * explicit request ("keyboard |", approved iteration 2). */
export function CenterBar(props: CenterBarProps) {
  return (
    <svg viewBox="0 0 24 24" fill="currentColor" xmlns="http://www.w3.org/2000/svg" {...props}>
      <rect x="10.8" y="4" width="2.4" height="16" rx="1.2" />
    </svg>
  );
}
