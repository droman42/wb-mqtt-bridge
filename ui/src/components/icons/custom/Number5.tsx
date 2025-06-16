import React from 'react';
import { NumberIcon } from './Number';

interface NumberIcon5Props extends React.SVGProps<SVGSVGElement> {}

export function NumberIcon5(props: NumberIcon5Props) {
  return <NumberIcon number="5" {...props} />;
} 