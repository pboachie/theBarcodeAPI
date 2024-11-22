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
};