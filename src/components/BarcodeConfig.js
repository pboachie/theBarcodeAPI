// src/components/BarcodeConfig.js

import React from 'react';
import { useSelector } from 'react-redux';
import { Card, CardHeader, CardContent } from '../components/ui/card';
import BarcodeTypeSelect from './BarcodeTypeSelect';
import BarcodeDataInput from './BarcodeDataInput';
import BarcodeSizeSlider from './BarcodeSizeSlider';
import ImageFormatSelect from './ImageFormatSelect';
import DPISlider from './DPISlider';
import CenterTextSwitch from './CenterTextSwitch';

const BarcodeConfig = () => {
  const isLimitExceeded = useSelector((state) => state.barcode.isLimitExceeded);

  return (
    <Card className={`bg-white shadow-lg ${isLimitExceeded ? 'opacity-50' : ''}`}>
      <CardHeader>
        <h2 className="text-xl font-semibold">Barcode Configuration</h2>
      </CardHeader>
      <CardContent>
        <div className="space-y-4">
          <BarcodeTypeSelect />
          <BarcodeDataInput />
          <BarcodeSizeSlider type="width" />
          <BarcodeSizeSlider type="height" />
          <ImageFormatSelect />
          <DPISlider />
          <CenterTextSwitch />
        </div>
      </CardContent>
    </Card>
  );
};

export default BarcodeConfig;
