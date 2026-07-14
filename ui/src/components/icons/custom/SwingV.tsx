import React from 'react';

type SwingVProps = React.SVGProps<SVGSVGElement>;

/** UI-16: vane (vertical) swing — three DETACHED rays fanning through the sweep
 * angles, convergence implied off-glyph, matching the firmware's ⚟ (approved in
 * the icon review, iteration 3: "don't join the rays at one point"). */
export function SwingV(props: SwingVProps) {
  return (
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2.2}
         strokeLinecap="round" xmlns="http://www.w3.org/2000/svg" {...props}>
      <path d="M7.2 9.2 L19.2 5.2" />
      <path d="M6.2 12 L20 12" />
      <path d="M7.2 14.8 L19.2 18.8" />
    </svg>
  );
}
