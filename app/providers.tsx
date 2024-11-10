// app/providers.tsx

'use client';

import { NextUIProvider } from '@nextui-org/react';
import { ReactNode } from 'react';
import { Toaster } from '@/components/ui/toaster';
import { Footer } from '@/components/layout/Footer';

export function Providers({ children }: { children: ReactNode }) {
  return (
    <NextUIProvider>
      {children}
      <Toaster />
      <Footer />
    </NextUIProvider>
  );
}