import React from 'react';

interface PowerOffProps extends React.SVGProps<SVGSVGElement> {}

export function PowerOff(props: PowerOffProps) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="currentColor"
      xmlns="http://www.w3.org/2000/svg"
      {...props}
    >
      {/* Power button vertical line */}
      <path d="M11 3h2v10h-2z" />
      
      {/* Power symbol arc */}
      <path d="M17.83 7.17l-1.42-1.42A7.007 7.007 0 0 1 19 11.5c0 3.86-3.14 7-7 7s-7-3.14-7-7a7.007 7.007 0 0 1 2.59-5.39L5.17 7.17A8.997 8.997 0 0 0 3 11.5c0 4.97 4.03 9 9 9s9-4.03 9-9a8.997 8.997 0 0 0-3.17-6.83z" />
    </svg>
  );
} 