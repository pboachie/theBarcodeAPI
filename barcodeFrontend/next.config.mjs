/** @type {import('next').NextConfig} */
const nextConfig = {
    reactStrictMode: true,
    images: {
      domains: ['thebarcodeapi.com', 'localhost', 'api.thebarcodeapi.com'],
    },
    async rewrites() {
    const isDevelopment = process.env.NODE_ENV === 'development';
    const apiUrl = isDevelopment ? 'http://barcodeapi:8000/api/v1' : 'https://api.thebarcodeapi.com/api/v1';

    return [
      {
        source: '/api/:path*',
        destination: `${apiUrl}/:path*`,
      },
    ];
    },
  }

  export default nextConfig