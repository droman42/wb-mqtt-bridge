import React from 'react';
import { NumberIcon } from './Number';

interface NumberIcon3Props extends React.SVGProps<SVGSVGElement> {}

export function NumberIcon3(props: NumberIcon3Props) {
  return <NumberIcon number="3" {...props} />;
} 