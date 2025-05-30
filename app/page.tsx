// app/page.tsx

import React from 'react';
import { Metadata } from 'next';
import BarcodePageClient from '@/components/barcode/BarcodePageClient';

export const metadata: Metadata = {
  title: 'the Barcode API',
  description: 'Generate barcodes quickly and easily with our free online tool',
  openGraph: {
    title: 'the Barcode API | theBarcodeAPI',
    description: 'Generate barcodes quickly and easily with our free online tool',
  },
};

export default function BarcodePage() {
  return <BarcodePageClient />;
}