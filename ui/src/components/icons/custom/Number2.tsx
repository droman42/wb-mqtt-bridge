import React from 'react';
import { NumberIcon } from './Number';

interface NumberIcon2Props extends React.SVGProps<SVGSVGElement> {}

export function NumberIcon2(props: NumberIcon2Props) {
  return <NumberIcon number="2" {...props} />;
} 