import React from 'react';

interface AutoRecycleProps extends React.SVGProps<SVGSVGElement> {}

/** UI-16: the HVAC "auto" value icon — three chasing arrows, faithful to the
 * mitsubishi2wb firmware's ♻ glyph (approved in the icon review, iteration 2). */
export function AutoRecycle(props: AutoRecycleProps) {
  const side = (
    <>
      <path d="M7.2 16.4 h6.2 v2.2 h-7.5 c-.9 0 -1.45 -1 -.95 -1.75 l1.8 -3.1 1.9 1.1 z" />
      <path d="M13 15.2 l4.6 2.3 -4.6 2.3 z" />
    </>
  );
  return (
    <svg viewBox="0 0 24 24" fill="currentColor" xmlns="http://www.w3.org/2000/svg" {...props}>
      <g transform="rotate(0 12 12)">{side}</g>
      <g transform="rotate(120 12 12)">{side}</g>
      <g transform="rotate(240 12 12)">{side}</g>
    </svg>
  );
}
