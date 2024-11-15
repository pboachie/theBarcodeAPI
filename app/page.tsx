// app/page.tsx

import React from 'react';
import dynamic from 'next/dynamic';
import { Metadata } from 'next';

const BarcodeGenerator = dynamic(() => import('@/components/barcode/BarcodeGenerator'), {
  ssr: false,
  loading: () => (
    <div className="flex items-center justify-center min-h-[400px]">
      <p>Loading...</p>
    </div>
  )
});

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
    <div className="min-h-screen bg-background">
      <main className="container mx-auto">
        <BarcodeGenerator />
      </main>
    </div>
  );
}