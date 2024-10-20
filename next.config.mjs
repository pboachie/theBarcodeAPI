/** @type {import('next').NextConfig} */
const nextConfig = {
    reactStrictMode: true,
    images: {
      domains: ['thebarcodeapi.com', 'localhost'],
    },
    async rewrites() {
    const isDevelopment = process.env.NODE_ENV === 'development';
    const apiUrl = isDevelopment ? 'http://localhost:3000/api' : 'https://thebarcodeapi.com/api';

    return [
      {
        source: '/api/barcode/:path*',
        destination: `${apiUrl}/:path*`,
      },
    ];
    },
  }

  export default nextConfig