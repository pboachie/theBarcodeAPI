import type { Metadata } from "next";
import localFont from "next/font/local";
import "../styles/globals.css";
import React from "react";
import { Toaster } from "@/components/ui/toaster";

const geistSans = localFont({
  src: "./fonts/GeistVF.woff",
  variable: "--font-geist-sans",
  weight: "100 900",
});
const geistMono = localFont({
  src: "./fonts/GeistMonoVF.woff",
  variable: "--font-geist-mono",
  weight: "100 900",
});

export const metadata: Metadata = {
  title: "The Barcode API",
  description: "Generate barcodes for free with The Barcode API. Supports various formats like code128, ean, isbn, and more. Easy, fast, and reliable.",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en">
      <body
        className={`${geistSans.variable} ${geistMono.variable} antialiased bg-cream`}
      >
        {children}
        <Toaster />
      </body>
    </html>
  );
}
