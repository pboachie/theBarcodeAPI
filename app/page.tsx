// app/page.tsx

import React from 'react';
import dynamic from 'next/dynamic';
import { Metadata } from 'next';

const BarcodeGenerator = dynamic(
  () => import('@/components/barcode/BarcodeGenerator'),
  { ssr: false }
);

export const metadata: Metadata = {
  title: 'Barcode Generator',
  description: 'Generate barcodes quickly and easily with our free online tool',
  openGraph: {
    title: 'Barcode Generator | The Barcode API',
    description: 'Generate barcodes quickly and easily with our free online tool',
  },
};

export default function BarcodePage() {
  return (
    <main className="min-h-screen bg-background">
      <BarcodeGenerator />
    </main>
  );
}
