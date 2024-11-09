
//next-seo.config.js

const title = 'The Barcode API - Generate Free Barcodes Online';
const description = 'The best free Barcode API to generate free barcodes online. Fast, reliable, and easy to use.';

export default {
  title,
  description,
  canonical: 'https://www.thebarcodeapi.com/',
  openGraph: {
    url: 'https://qqq.thebarcodeapi.com/',
    locale: 'en_US',
    title,
    description,
    images: [
      {
        url: 'https://thebarcodeapi.com/og-image.png',
        width: 600,
        height: 330,
        alt: 'The Barcode API - Generate Free Barcodes Online',
      },
    ],
    site_name: 'The Barcode API',
  },
  twitter: {
    handle: '@thebarcodeapi',
    site: '@thebarcodeapi',
    cardType: 'summary_large_image',
  },
};