import React from 'react';
import { Number } from './Number';

interface Number5Props extends React.SVGProps<SVGSVGElement> {}

export function Number5(props: Number5Props) {
  return <Number number="5" {...props} />;
} 