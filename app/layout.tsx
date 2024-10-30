import { Toaster } from '@/components/ui/toaster';
import { geistSans, geistMono } from '@/app/styles/fonts';
import '../app/styles/globals.css';

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className={`${geistSans.variable} ${geistMono.variable}`}>
      <body className="antialiased bg-cream">
        {children}
        <Toaster />
      </body>
    </html>
  );
}
