// barcodeConfig.ts

import { BarcodeType } from './types';

export const barcodeTextMap: { [key in BarcodeType | 'default']: string } = {
    ean13: '123456789123',
    code39: 'ABC 1234',
    ean: '5901234123457',
    ean8: '1234567',
    jan: '453456999999',
    itf: '01234567890123',
    ean14: '1234567890123',
    upc: '12345678901',
    upca: '01234567890',
    isbn: '9781234567890',
    isbn10: '123456789',
    isbn13: '978123456789',
    gs1_128: '0101234567890128BAR-IT',
    gtin: '01234567890128',
    issn: '1234567',
    pzn: '123456',
    default: 'Change Me!',
    code128: '',
    gs1: ''
};

export const getBarcodeText = (type: BarcodeType, data?: string): string => {
  if (data && data.trim() !== '') {
    return data;
  }
  return barcodeTextMap[type] || barcodeTextMap['default'];
};