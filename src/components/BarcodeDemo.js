// src/components/BarcodeDemo.js

import React from 'react';
import { useSelector } from 'react-redux';
import BarcodeConfig from './BarcodeConfig';
import BarcodePreview from './BarcodePreview';

const BarcodeDemo = () => {
  const isLimitExceeded = useSelector(state => state.barcode.isLimitExceeded);

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
      <BarcodeConfig />
      <BarcodePreview />
    </div>
  );
};

export default BarcodeDemo;