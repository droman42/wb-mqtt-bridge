import React from 'react';

interface PlayPauseProps extends React.SVGProps<SVGSVGElement> {}

export function PlayPause(props: PlayPauseProps) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="currentColor"
      xmlns="http://www.w3.org/2000/svg"
      {...props}
    >
      {/* Combined play-pause icon design */}
      {/* Left side: Pause (bar) */}
      <path d="M4 4h3v16H4z" />
      
      {/* Right side: Play (triangle) */}
      <path d="M10 4l9 8-9 8z" />
    </svg>
  );
} 