// app/layout.tsx

import { geistSans, geistMono } from '@/app/styles/fonts';
import '../app/styles/globals.css';
import { ReactNode } from 'react';
import { Providers } from './providers';
import { Metadata, Viewport } from 'next';
import type { OpenGraph } from 'next/dist/lib/metadata/types/opengraph-types';
import type { Twitter } from 'next/dist/lib/metadata/types/twitter-types';

interface RootLayoutProps {
  children: ReactNode;
}

interface StructuredData {
  "@context": string;
  "@type": string;
  url: string;
  name: string;
  description: string;
  publisher: {
    "@type": string;
    name: string;
    logo: {
      "@type": string;
      url: string;
    };
  };
  potentialAction: {
    "@type": string;
    target: string;
    "query-input": string;
  };
}

const siteConfig = {
  title: 'Free Barcode API - Generate EAN, GS1, UPC Barcodes Online',
  description: 'Use our free barcode API to generate EAN, GS1, UPC, and other barcodes online. Fast, reliable, and easy to use.',
  url: 'https://www.thebarcodeapi.com',
} as const;

export const metadata = {
  metadataBase: new URL(siteConfig.url),
  title: {
    default: siteConfig.title,
    template: `%s | The Barcode API`,
  },
  description: siteConfig.description,
  keywords: [
    // Core Service Keywords
    'Free Barcode API',
    'Barcode Generator',
    'Online Barcode',
    'Barcode API',
    'Free Barcode Generator',
    'Online Barcode Generator',
    'API Barcode Generator',
    'REST Barcode API',
    'HTTP Barcode API',

    // Barcode Types
    'EAN',
    'EAN-13',
    'EAN-8',
    'UPC',
    'UPC-A',
    'UPC-E',
    'GS1',
    'GS1-128',
    'Code 128',
    'Code 39',
    'Code 93',
    'Codabar',
    'ITF',
    'ITF-14',
    'QR Code',
    'DataMatrix',
    'PDF417',
    'ISBN',
    'ISSN',
    'GTIN',

    // Use Cases
    'Product Barcodes',
    'Retail Barcodes',
    'Inventory Barcodes',
    'Shipping Barcodes',
    'Package Tracking',
    'Asset Tracking',
    'Warehouse Management',
    'Supply Chain',
    'POS System',

    // Technical Terms
    'Barcode Integration',
    'Barcode Web Service',
    'Barcode Generation Service',
    'Programmatic Barcode Generation',
    'Developer Barcode Tools',
    'Barcode Development API',
    'REST API Barcodes',
    'JSON Barcode Response',
    'SVG Barcodes',
    'PNG Barcodes',

    // Industry Terms
    'Retail Barcode Solution',
    'E-commerce Barcodes',
    'Logistics Barcodes',
    'Inventory Management',
    'Supply Chain Management',
    'Asset Management',

    // Features
    'High Resolution Barcodes',
    'Vector Barcodes',
    'Scalable Barcodes',
    'Customizable Barcodes',
    'Bulk Barcode Generation',
    'Barcode Validation',
    'Barcode Verification',

    // Quality Terms
    'Professional Barcodes',
    'Commercial Grade Barcodes',
    'Industry Standard Barcodes',
    'GS1 Compliant',
    'ISO Compliant',

    // Generic Terms
    'Generate Barcodes',
    'Create Barcodes',
    'Make Barcodes',
    'Print Barcodes',
    'Download Barcodes',
    'Custom Barcodes',
    'Digital Barcodes'
  ],
  openGraph: {
    type: 'website',
    locale: 'en_US',
    url: siteConfig.url,
    siteName: 'The Barcode API',
    title: 'Free Barcode API - Generate EAN, GS1, UPC Online',
    description: 'Generate EAN, GS1, UPC, and other barcodes for free with The Barcode API.',
    images: [
      {
        url: '/og-image.png',
        width: 1200,
        height: 630,
        alt: 'The Barcode API',
      },
    ],
  } satisfies OpenGraph,
  twitter: {
    card: 'summary_large_image',
    site: '@thebarcodeapi',
    creator: '@thebarcodeapi',
    title: 'Free Barcode API - Generate Barcodes Online',
    description: 'Generate EAN, GS1, UPC, and more barcodes for free using our online API.',
    images: ['/og-image.png']
  } satisfies Twitter,
  icons: {
    icon: [{ url: '/favicon.ico' }],
  },
} satisfies Metadata;

export const viewport: Viewport = {
  width: 'device-width',
  initialScale: 1,
};

const structuredData: StructuredData = {
  "@context": "https://schema.org",
  "@type": "WebSite",
  "url": siteConfig.url,
  "name": "The Barcode API",
  "description": siteConfig.description,
  "publisher": {
    "@type": "Organization",
    "name": "The Barcode API",
    "logo": {
      "@type": "ImageObject",
      "url": `${siteConfig.url}/og-image.png`
    }
  },
  "potentialAction": {
    "@type": "SearchAction",
    "target": `${siteConfig.url}/?s={search_term_string}`,
    "query-input": "required name=search_term_string"
  }
};

export default function RootLayout({ children }: RootLayoutProps) {
  const ogImage = metadata.openGraph?.images?.[0];
  const twitterImage = metadata.twitter?.images?.[0];

  return (
    <html lang="en" className={`${geistSans.variable} ${geistMono.variable}`}>
      <head>
        <meta name="description" content={metadata.description} />
        <meta name="keywords" content={metadata.keywords?.join(', ')} />

        {/* OpenGraph */}
        <meta property="og:type" content={metadata.openGraph?.type} />
        <meta property="og:locale" content={metadata.openGraph?.locale} />
        <meta property="og:url" content={metadata.openGraph?.url} />
        <meta property="og:site_name" content={metadata.openGraph?.siteName} />
        <meta property="og:title" content={metadata.openGraph?.title} />
        <meta property="og:description" content={metadata.openGraph?.description} />
        {typeof ogImage === 'string' ? (
          <meta property="og:image" content={ogImage} />
        ) : (
          <>
            <meta property="og:image" content={ogImage?.url} />
            <meta property="og:image:width" content={ogImage?.width?.toString()} />
            <meta property="og:image:height" content={ogImage?.height?.toString()} />
            <meta property="og:image:alt" content={ogImage?.alt} />
          </>
        )}

        {/* Twitter */}
        <meta name="twitter:card" content={metadata.twitter?.card} />
        <meta name="twitter:site" content={metadata.twitter?.site} />
        <meta name="twitter:creator" content={metadata.twitter?.creator} />
        <meta name="twitter:title" content={metadata.twitter?.title} />
        <meta name="twitter:description" content={metadata.twitter?.description} />
        <meta name="twitter:image" content={typeof twitterImage === 'string' ? twitterImage : (twitterImage as { images: string })?.images} />

        {/* Icons */}
        <link rel="icon" href={metadata.icons?.icon?.[0]?.url} />

        {/* Structured Data */}
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={{ __html: JSON.stringify(structuredData) }}
        />
      </head>
      <body className="antialiased bg-background">
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}