import React from 'react';

interface NumberIconProps extends React.SVGProps<SVGSVGElement> {
  number: string | number;
}

export function NumberIcon({ number, ...props }: NumberIconProps) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="currentColor"
      xmlns="http://www.w3.org/2000/svg"
      {...props}
    >
      {/* Button background */}
      <rect x="3" y="3" width="18" height="18" rx="3" fill="none" stroke="currentColor" strokeWidth="1.5" opacity="0.6" />
      
      {/* Number text */}
      <text
        x="12"
        y="16"
        textAnchor="middle"
        fontSize="10"
        fontWeight="bold"
        fill="currentColor"
        fontFamily="system-ui, -apple-system, sans-serif"
      >
        {number}
      </text>
    </svg>
  );
} 