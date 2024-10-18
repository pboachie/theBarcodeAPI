import React from 'react';
import { useSelector, useDispatch } from 'react-redux';
import { setBarcodeType } from '../slices/barcodeSlice';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '../components/ui/select';

const BarcodeTypeSelect = () => {
  const dispatch = useDispatch();
  const { barcodeType, isLimitExceeded } = useSelector((state) => state.barcode);

  const barcodeTypes = [
    'code128',
    'code39',
    'ean',
    'ean13',
    'ean14',
    'ean8',
    'gs1',
    'gs1_128',
    'gtin',
    'isbn',
    'isbn10',
    'isbn13',
    'issn',
    'itf',
    'jan',
    'pzn',
    'upc',
    'upca',
  ];

  return (
    <div>
      <label className="block text-sm font-medium mb-1">Barcode Type</label>
      <Select
        value={barcodeType}
        onValueChange={(value) => dispatch(setBarcodeType(value))}
        disabled={isLimitExceeded}
      >
        <SelectTrigger className="w-full">
          <SelectValue placeholder="Select barcode type" />
        </SelectTrigger>
        <SelectContent>
          {barcodeTypes.map((type) => (
            <SelectItem key={type} value={type}>
              {type}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    </div>
  );
};

export default BarcodeTypeSelect;
