//src/components/BarcodeDataInput.js

import React from 'react';
import { useSelector, useDispatch } from 'react-redux';
import { setBarcodeText } from '../slices/barcodeSlice';

const BarcodeDataInput = () => {
  const dispatch = useDispatch();
  const { barcodeText, barcodeType, isLimitExceeded } = useSelector((state) => state.barcode);

  const maxChars = {
    ean13: 12,
    ean8: 7,
    ean14: 13,
    upca: 11,
    isbn10: 9,
    isbn13: 12,
    issn: 7,
    pzn: 6,
  };

  const handleChange = (e) => {
    const newText = e.target.value;
    if (maxChars[barcodeType]) {
      dispatch(setBarcodeText(newText.slice(0, maxChars[barcodeType])));
    } else {
      dispatch(setBarcodeText(newText));
    }
  };

  return (
    <div>
      <label className="block text-sm font-medium mb-1">
        Barcode Content
        {maxChars[barcodeType] && ` (Max ${maxChars[barcodeType]} characters)`}
      </label>
      <input
        type="text"
        value={barcodeText}
        onChange={handleChange}
        className="w-full p-2 border rounded"
        placeholder={`Enter ${barcodeType} content`}
        disabled={isLimitExceeded}
      />
    </div>
  );
};

export default BarcodeDataInput;
