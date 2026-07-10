import React from 'react';

interface SwingHProps extends React.SVGProps<SVGSVGElement> {}

/** UI-16: widevane (horizontal) swing — the 90°-rotated pair of SwingV: detached
 * rays fanning left/right, pivot implied above (approved iteration 3). */
export function SwingH(props: SwingHProps) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2.2}
         strokeLinecap="round" xmlns="http://www.w3.org/2000/svg" {...props}>
      <path d="M9.2 7.2 L5.2 19.2" />
      <path d="M12 6.2 L12 20" />
      <path d="M14.8 7.2 L18.8 19.2" />
    </svg>
  );
}
