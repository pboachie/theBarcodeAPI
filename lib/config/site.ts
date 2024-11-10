// lib/config/site.ts

export const siteConfig = {
    name: "The Barcode API",
    description: "Generate Free Barcodes Online",
    url: "https://thebarcodeapi.com",
    footer: {
      navigation: [
        { href: '/', label: 'Home' },
        { href: '/mass-generate', label: 'Upload', longLabel: 'Mass Generate' },
        { href: '/docs', label: 'Docs', longLabel: 'API Documentation' },
        { href: '/support', label: 'Support' }
      ],
      social: [
        {
          href: "https://twitter.com/thebarcodeapi",
          label: "Follow us on Twitter",
          platform: 'twitter'
        },
        {
          href: "mailto:support@thebarcodeapi.com",
          label: "Contact Support via Email",
          platform: 'email'
        }
      ]
    }
  } as const;
