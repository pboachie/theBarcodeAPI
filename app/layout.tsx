// app/layout.tsx

import { geistSans, geistMono } from '@/app/styles/fonts';
import '../app/styles/globals.css';
import { ReactNode } from 'react';
import { Providers } from './providers';
import { Metadata, Viewport } from 'next';

interface RootLayoutProps {
  children: ReactNode;
}

export const metadata: Metadata = {
  title: {
    default: 'The Barcode API - Generate Free Barcodes Online',
    template: '%s | The Barcode API',
  },
  description: 'The best free Barcode API to generate free barcodes online. Fast, reliable, and easy to use.',
  openGraph: {
    type: 'website',
    locale: 'en_US',
    url: 'https://www.thebarcodeapi.com/',
    siteName: 'The Barcode API',
    title: 'The Barcode API - Generate Free Barcodes Online',
    description: 'The best free Barcode API to generate free barcodes online. Fast, reliable, and easy to use.',
    images: [{
      url: 'https://thebarcodeapi.com/og-image.png',
      width: 1200,
      height: 630,
      alt: 'The Barcode API',
    }],
  },
  twitter: {
    card: 'summary_large_image',
    site: '@thebarcodeapi',
    creator: '@thebarcodeapi',
  },
  icons: {
    icon: '/favicon.ico',
  },
};

export const viewport: Viewport = {
  width: 'device-width',
  initialScale: 1,
};

export default function RootLayout({ children }: RootLayoutProps) {
  return (
    <html lang="en" className={`${geistSans.variable} ${geistMono.variable}`}>
      <body className="antialiased bg-cream">
        <Providers>
          {children}
        </Providers>
      </body>
    </html>
  );
}
