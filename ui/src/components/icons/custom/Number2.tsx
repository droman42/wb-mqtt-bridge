import React from 'react';
import { Number } from './Number';

interface Number2Props extends React.SVGProps<SVGSVGElement> {}

export function Number2(props: Number2Props) {
  return <Number number="2" {...props} />;
} 