// app/providers.tsx

'use client';

import { NextUIProvider } from '@nextui-org/react';
import { ReactNode } from 'react';
import { Toaster } from '@/components/ui/toaster';
import { Footer } from '@/components/layout/Footer';

export function Providers({ children }: { children: ReactNode }) {
  return (
    <NextUIProvider>
      <div className="flex flex-col min-h-screen">
        <div className="flex-grow">
          {children}
        </div>
        <Toaster />
        <Footer />
      </div>
    </NextUIProvider>
  );
}