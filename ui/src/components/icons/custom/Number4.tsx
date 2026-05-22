import React from 'react';
import { NumberIcon } from './Number';

interface NumberIcon4Props extends React.SVGProps<SVGSVGElement> {}

export function NumberIcon4(props: NumberIcon4Props) {
  return <NumberIcon number="4" {...props} />;
} 