import { writeFileSync } from 'fs';
import { join } from 'path';
import process from 'node:process';

// SportsEsports Material Icon path data (cleaner version)
const sportsEsportsPath = 'M21.58 16.09l-1.09-7.66C20.21 6.46 18.52 5 16.53 5H7.47C5.48 5 3.79 6.46 3.51 8.43l-1.09 7.66c-.3 2.1 1.28 4.91 3.49 4.91H7.5c.73 0 1.39-.37 1.78-.95L12 16.58l2.72 3.47c.39.58 1.05.95 1.78.95h1.59c2.21 0 3.79-2.81 3.49-4.91zM9 9c0 .55-.45 1-1 1s-1-.45-1-1 .45-1 1-1 1 .45 1 1zm8 0c0 .55-.45 1-1 1s-1-.45-1-1 .45-1 1-1 1 .45 1 1z';

// Create different sized SVG favicons
const createFavicon = (size) => `<?xml version="1.0" encoding="UTF-8"?>
<svg width="${size}" height="${size}" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
  <path d="${sportsEsportsPath}" fill="#3B82F6"/>
</svg>`;

// Write favicons to public directory
const publicDir = join(process.cwd(), 'public');

// Standard favicon
writeFileSync(join(publicDir, 'favicon.svg'), createFavicon(32));

// Different sizes for various uses
writeFileSync(join(publicDir, 'favicon-16x16.svg'), createFavicon(16));
writeFileSync(join(publicDir, 'favicon-32x32.svg'), createFavicon(32));
writeFileSync(join(publicDir, 'apple-touch-icon.svg'), createFavicon(180));

console.log('✅ SportsEsports favicons generated successfully!');
console.log('📁 Generated files:');
console.log('   - public/favicon.svg (32x32)');
console.log('   - public/favicon-16x16.svg');
console.log('   - public/favicon-32x32.svg');
console.log('   - public/apple-touch-icon.svg (180x180)');
console.log('🎮 Gaming-themed favicon ready!'); 