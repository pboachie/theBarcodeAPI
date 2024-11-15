// app/layout.tsx

import { geistSans, geistMono } from '@/app/styles/fonts';
import '../app/styles/globals.css';
import { ReactNode } from 'react';
import { Providers } from './providers';
import { Metadata, Viewport } from 'next';
import type { OpenGraph } from 'next/dist/lib/metadata/types/opengraph-types';
import type { Twitter } from 'next/dist/lib/metadata/types/twitter-types';
import { siteConfig } from '@/lib/config/site';

interface RootLayoutProps {
  children: ReactNode;
}

interface StructuredData {
  "@context": string;
  "@type": string;
  url: string;
  name: string;
  description: string;
  applicationCategory: string;
  operatingSystem: string;
  offers: {
    "@type": string;
    price: string;
    priceCurrency: string;
  };
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
  featureList: string[];
  mainEntityOfPage?: {
    "@type": string;
    "@id": string;
  };
  inLanguage?: string;
  datePublished?: string;
  dateModified?: string;
  author?: {
    "@type": string;
    name: string;
  };
  image?: {
    "@type": string;
    url: string;
    width: number;
    height: number;
  };
}

export const metadata = {
  metadataBase: new URL(siteConfig.url),
  title: {
    default: siteConfig.title,
    template: `%s | The Barcode API`,
  },
  description: siteConfig.description,
  keywords: [...siteConfig.keywords],
  openGraph: {
    type: siteConfig.type,
    locale: siteConfig.locale,
    url: siteConfig.url,
    siteName: siteConfig.name,
    title: siteConfig.title,
    description: siteConfig.description,
    images: [
      {
        url: siteConfig.images.ogImage,
        width: 1200,
        height: 630,
        alt: siteConfig.name,
      },
    ],
  } satisfies OpenGraph,
  twitter: {
    card: 'summary_large_image',
    site: '@thebarcodeapi',
    creator: '@thebarcodeapi',
    title: siteConfig.title,
    description: siteConfig.description,
    images: siteConfig.images.ogImage,
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
  "name": siteConfig.name,
  "description": siteConfig.description,
  "applicationCategory": "BusinessApplication",
  "operatingSystem": "All",
  "offers": {
    "@type": "Offer",
    "price": "0",
    "priceCurrency": "USD"
  },
  "publisher": {
    "@type": "Organization",
    "name": siteConfig.name,
    "logo": {
      "@type": "ImageObject",
      "url": `${siteConfig.url}/${siteConfig.images.ogImage}`
    }
  },
  "potentialAction": {
    "@type": "SearchAction",
    "target": `${siteConfig.url}/?s={search_term_string}`,
    "query-input": "required name=search_term_string"
  },
  "featureList": [
    "Free barcode generation",
    "Multiple barcode formats supported",
    "RESTful API",
    "No registration required",
    "High resolution output",
    "Customizable options"
  ],
  "mainEntityOfPage": {
    "@type": "WebPage",
    "@id": siteConfig.url
  },
  "inLanguage": siteConfig.locale,
  "datePublished": "2023-01-01",
  "dateModified": new Date().toISOString(),
  "author": {
    "@type": "Organization",
    "name": siteConfig.name
  },
  "image": {
    "@type": "ImageObject",
    "url": `${siteConfig.url}/${siteConfig.images.ogImage}`,
    "width": 1200,
    "height": 630
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