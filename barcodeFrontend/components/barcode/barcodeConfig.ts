
// barcodeConfig.ts

import { BarcodeType } from '@/components/types/barcode';

export const barcodeTextMap: { [key in BarcodeType | 'default']: string } = {
    ean13: '1234567890128',
    code39: 'CODE39 SAMPLE',
    ean: '5901234123457',
    ean8: '96385074',
    jan: '49123456',
    itf: '123456789012',
    ean14: '12345678901231',
    upc: '123456789012',
    upca: '036000291452',
    isbn: '9783161484100',
    isbn10: '316148410X',
    isbn13: '9783161484100',
    gs1_128: '0101234567890128',
    gtin: '00123456789012',
    issn: '9771234567003',
    pzn: '1234567',
    code128: 'CODE128 SAMPLE',
    gs1: '(01)12345678901231',
    default: 'SAMPLE BARCODE'
};

export const getBarcodeText = (type: BarcodeType, data?: string): string => {
  if (data && data.trim() !== '') {
    return data;
  }
  return barcodeTextMap[type] || barcodeTextMap['default'];
};