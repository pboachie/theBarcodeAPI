// components/types/barcode.ts

export type BarcodeType = typeof barcodeTypes[number];
export type ImageFormat = typeof imageFormats[number];

export const barcodeTypes = [
  'code128', 'code39', 'ean', 'ean13', 'ean14', 'ean8', 'gs1', 'gs1_128',
  'gtin', 'isbn', 'isbn10', 'isbn13', 'issn', 'itf', 'jan', 'pzn', 'upc', 'upca'
] as const;

export const imageFormats = ['BMP', 'GIF', 'JPEG', 'PNG'] as const;

export const maxChars = {
  ean13: 12,
  ean8: 7,
  ean14: 13,
  ean: 13,
  jan: 13,
  gtin: 14,
  upc: 12,
  upca: 11,
  isbn: 13,
  isbn10: 9,
  isbn13: 12,
  itf: 14,
  issn: 7,
  pzn: 6,
  code39: 43,
  gs1_128: 48,
} as const;
