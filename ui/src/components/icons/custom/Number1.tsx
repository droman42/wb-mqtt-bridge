import React from 'react';
import { Number } from './Number';

interface Number1Props extends React.SVGProps<SVGSVGElement> {}

export function Number1(props: Number1Props) {
  return <Number number="1" {...props} />;
} 