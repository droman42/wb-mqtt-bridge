import React from 'react';

interface TrayOpenProps extends React.SVGProps<SVGSVGElement> {}

export function TrayOpen(props: TrayOpenProps) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="currentColor"
      xmlns="http://www.w3.org/2000/svg"
      {...props}
    >
      {/* Device body */}
      <rect x="2" y="8" width="12" height="8" rx="1" fill="currentColor" opacity="0.7" />
      
      {/* Extended tray */}
      <rect x="14" y="10" width="8" height="4" rx="0.5" fill="currentColor" />
      
      {/* Disc on tray */}
      <circle cx="18" cy="12" r="1.5" fill="none" stroke="currentColor" strokeWidth="0.5" />
      <circle cx="18" cy="12" r="0.3" fill="currentColor" />
      
      {/* Tray edge indicator */}
      <line x1="14" y1="10" x2="14" y2="14" stroke="currentColor" strokeWidth="0.5" opacity="0.8" />
    </svg>
  );
} 