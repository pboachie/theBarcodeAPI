// app/providers.tsx

'use client';

import { NextUIProvider } from '@nextui-org/react';
import { ReactNode } from 'react';
import { Toaster } from '@/components/ui/toaster';
import { Footer } from '@/components/layout/Footer';

export function Providers({ children }: { children: ReactNode }) {
  return (
    <NextUIProvider>
      <div className="flex min-h-screen flex-col">
        <div className="flex-1">
          {children}
        </div>
        <Footer />
        <Toaster />
      </div>
    </NextUIProvider>
  );
}