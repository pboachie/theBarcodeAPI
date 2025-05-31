/** @type {import('next-sitemap').IConfig} */
module.exports = {
  siteUrl: 'https://www.thebarcodeapi.com',
  generateRobotsTxt: true,
  sitemapSize: 7000,
  changefreq: 'daily',
  priority: 0.7,
  robotsTxtOptions: {
    additionalSitemaps: [
      'https://www.thebarcodeapi.com/sitemap.xml',
      'https://www.thebarcodeapi.com/sitemap-0.xml',
    ],
  },
  additionalPaths: async (config) => {
    return [
      {
        loc: 'https://api.thebarcodeapi.com',
        changefreq: 'daily',
        priority: 0.7,
        lastmod: new Date().toISOString(),
      },
      // Add other manual paths here if needed in the future
    ];
  },
};