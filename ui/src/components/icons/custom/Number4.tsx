import React from 'react';
import { Number } from './Number';

interface Number4Props extends React.SVGProps<SVGSVGElement> {}

export function Number4(props: Number4Props) {
  return <Number number="4" {...props} />;
} 