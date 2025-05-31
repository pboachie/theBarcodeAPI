// /app/styles/fonts.ts

import localFont from 'next/font/local';

const GeistSans = localFont({
  src: '../fonts/GeistVF.woff',
  variable: '--font-geist-sans',
});

const GeistMono = localFont({
  src: '../fonts/GeistMonoVF.woff',
  variable: '--font-geist-mono',
});

export const geistSans = GeistSans;

export const geistMono = GeistMono;
