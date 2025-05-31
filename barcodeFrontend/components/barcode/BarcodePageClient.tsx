'use client';

import React from 'react';
import dynamic from 'next/dynamic';

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

export default function BarcodePageClient() {
  return <BarcodeGenerator />;
}
