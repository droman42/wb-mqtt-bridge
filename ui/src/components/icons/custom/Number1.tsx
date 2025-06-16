import React from 'react';
import { NumberIcon } from './Number';

interface NumberIcon1Props extends React.SVGProps<SVGSVGElement> {}

export function NumberIcon1(props: NumberIcon1Props) {
  return <NumberIcon number="1" {...props} />;
} 