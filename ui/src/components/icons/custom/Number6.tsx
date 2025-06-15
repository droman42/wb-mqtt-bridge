import React from 'react';
import { Number } from './Number';

interface Number6Props extends React.SVGProps<SVGSVGElement> {}

export function Number6(props: Number6Props) {
  return <Number number="6" {...props} />;
} 