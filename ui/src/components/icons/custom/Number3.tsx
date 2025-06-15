import React from 'react';
import { Number } from './Number';

interface Number3Props extends React.SVGProps<SVGSVGElement> {}

export function Number3(props: Number3Props) {
  return <Number number="3" {...props} />;
} 