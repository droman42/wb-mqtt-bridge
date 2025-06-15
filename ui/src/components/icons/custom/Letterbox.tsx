import React from 'react';

interface LetterboxProps extends React.SVGProps<SVGSVGElement> {}

export function Letterbox(props: LetterboxProps) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="currentColor"
      xmlns="http://www.w3.org/2000/svg"
      {...props}
    >
      {/* Main rectangle frame */}
      <rect
        x={2}
        y={6}
        width={20}
        height={12}
        rx={2}
        ry={2}
        stroke="currentColor"
        strokeWidth={2}
        fill="none"
      />
      
      {/* Top letterbox bar */}
      <rect
        x={2}
        y={6}
        width={20}
        height={3}
        fill="currentColor"
      />
      
      {/* Bottom letterbox bar */}
      <rect
        x={2}
        y={15}
        width={20}
        height={3}
        fill="currentColor"
      />
    </svg>
  );
} 