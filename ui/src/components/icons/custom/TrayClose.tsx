import React from 'react';

interface TrayCloseProps extends React.SVGProps<SVGSVGElement> {}

export function TrayClose(props: TrayCloseProps) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="currentColor"
      xmlns="http://www.w3.org/2000/svg"
      {...props}
    >
      {/* Device body */}
      <rect x="4" y="8" width="16" height="8" rx="1" fill="currentColor" opacity="0.8" />
      
      {/* Closed tray slot */}
      <rect x="6" y="10" width="12" height="4" rx="0.5" fill="none" stroke="currentColor" strokeWidth="0.5" opacity="0.6" />
      
      {/* Disc inside (visible through slot) */}
      <circle cx="12" cy="12" r="1" fill="none" stroke="currentColor" strokeWidth="0.4" opacity="0.5" />
      <circle cx="12" cy="12" r="0.2" fill="currentColor" opacity="0.5" />
      
      {/* Tray slot indicator line */}
      <line x1="6" y1="12" x2="18" y2="12" stroke="currentColor" strokeWidth="0.3" opacity="0.4" />
    </svg>
  );
} 