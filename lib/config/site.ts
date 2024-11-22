// lib/config/site.ts

export const siteConfig = {
  name: "The Barcode API",
  title: 'Free Barcode API - Generate EAN, GS1, UPC Barcodes Online',
  description: 'Use our free barcode API to generate EAN, GS1, UPC, and other barcodes online. Fast, reliable, and easy to use.',
  url: 'https://www.thebarcodeapi.com',
  type: 'website',
  locale: 'en_US',
  footer: {
    navigation: [
    { href: '/', label: 'Home' },
    { href: '/mass-generate', label: 'Upload', longLabel: 'Mass Generate' },
    { href: 'https://api.thebarcodeapi.com', label: 'Docs', longLabel: 'API Documentation', target: '_blank' },
    { href: '/support', label: 'Support' }
    ],
    social: [
    {
      href: "https://twitter.com/thebarcodeapi",
      label: "Follow us on Twitter",
      platform: 'twitter',
      target: '_blank'
    },
    {
      href: "mailto:support@thebarcodeapi.com",
      label: "Contact Support via Email",
      platform: 'email'
    }
    ]
  },
  images: {
    logo: '/logo.svg',
    ogImage: '/og-image.png'
  },
  keywords: [
    // Core Service Keywords
    'Free Barcode API',
    'The Barcode API',
    'The Barcode API Free',
    'The Barcode API Online',
    'The Barcode API Generator',
    'The Barcode API com',
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
    'API Barcodes',
    'api.thebarcodeapi.com',
    'thebarcodeapi.com',

    'Generate Barcodes',
    'Create Barcodes',
    'Make Barcodes',
    'Print Barcodes',
    'Download Barcodes',
    'Custom Barcodes',
    'Digital Barcodes'
  ]
  } as const;
