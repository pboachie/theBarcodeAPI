// app/page.tsx

'use client';

import React from 'react';
import dynamic from 'next/dynamic';

// Dynamically import BarcodeGenerator to avoid SSR issues with window/navigator
const BarcodeGenerator = dynamic(
  () => import('@/components/barcode/BarcodeGenerator'),
  { ssr: false }
);

export default function BarcodePage() {
  return (
    <main className="min-h-screen bg-background">
      <BarcodeGenerator />
    </main>
  );
}