// lib/config/site.ts

export const siteConfig = {
    name: "The Barcode API",
    description: "Generate Free Barcodes Online",
    url: "https://thebarcodeapi.com",
    footer: {
      navigation: [
        { href: '/', label: 'Home' },
        { href: '/mass-generate', label: 'Mass Generate' },
        { href: '/docs', label: 'Docs', longLabel: 'API Documentation' },
        { href: '/contact', label: 'Contact Us' }
      ],
      social: [
        {
          href: "https://twitter.com/thebarcodeapi",
          label: "Follow us on Twitter",
          platform: 'twitter'
        },
        {
          href: "mailto:info@thebarcodeapi.com",
          label: "Contact us via email",
          platform: 'email'
        }
      ]
    }
  } as const;
