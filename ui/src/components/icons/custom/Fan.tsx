import React from 'react';

interface FanProps extends React.SVGProps<SVGSVGElement> {}

export function Fan(props: FanProps) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="currentColor"
      xmlns="http://www.w3.org/2000/svg"
      {...props}
    >
      {/* Fan center hub */}
      <circle cx="12" cy="12" r="2" fill="currentColor" />
      
      {/* Fan blades (4 curved blades) */}
      {/* Top blade */}
      <path d="M12 10 C8 6, 8 6, 10 2 C14 4, 14 8, 12 10" fill="currentColor" opacity="0.8" />
      
      {/* Right blade */}
      <path d="M14 12 C18 8, 18 8, 22 10 C20 14, 16 14, 14 12" fill="currentColor" opacity="0.8" />
      
      {/* Bottom blade */}
      <path d="M12 14 C16 18, 16 18, 14 22 C10 20, 10 16, 12 14" fill="currentColor" opacity="0.8" />
      
      {/* Left blade */}
      <path d="M10 12 C6 16, 6 16, 2 14 C4 10, 8 10, 10 12" fill="currentColor" opacity="0.8" />
      
      {/* Center dot */}
      <circle cx="12" cy="12" r="0.8" fill="currentColor" />
    </svg>
  );
} 