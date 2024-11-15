// app/page.tsx

import React from 'react';
import dynamic from 'next/dynamic';
import { Metadata } from 'next';

const BarcodeGenerator = dynamic(
  () => import('@/components/barcode/BarcodeGenerator'),
  {
    ssr: false,
    loading: () => (
      <div className="container mx-auto p-4">
        <div className="flex items-center justify-center min-h-[400px]">
          <p>Loading...</p>
        </div>
      </div>
    ),
  }
);

export const metadata: Metadata = {
  title: 'the Barcode API',
  description: 'Generate barcodes quickly and easily with our free online tool',
  openGraph: {
    title: 'the Barcode API | theBarcodeAPI',
    description: 'Generate barcodes quickly and easily with our free online tool',
  },
};

export default function BarcodePage() {
  return <BarcodeGenerator />;
}