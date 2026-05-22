import React from 'react';

interface AspectRatioProps extends React.SVGProps<SVGSVGElement> {
  ratio: string;
}

export function AspectRatio({ ratio, ...props }: AspectRatioProps) {
  // Parse the ratio string (e.g., "16:9", "4:3")
  const [width, height] = ratio.split(':').map(Number);
  
  // Calculate dimensions that maintain the aspect ratio
  const rectWidth = 20;
  const rectHeight = rectWidth * (height / width);
  
  // Calculate centered position
  const x = (24 - rectWidth) / 2;
  const y = (24 - rectHeight) / 2;

  return (
    <svg
      viewBox="0 0 24 24"
      fill="currentColor"
      xmlns="http://www.w3.org/2000/svg"
      {...props}
    >
      {/* Aspect ratio rectangle */}
      <rect
        x={x}
        y={y}
        width={rectWidth}
        height={rectHeight}
        rx={2}
        ry={2}
        stroke="currentColor"
        strokeWidth={2}
        fill="none"
      />
      
      {/* Ratio text */}
      <text
        x={12}
        y={12}
        fontSize={5}
        textAnchor="middle"
        dominantBaseline="middle"
        fill="currentColor"
        fontWeight={700}
      >
        {ratio}
      </text>
    </svg>
  );
} 