//src/componebts/DPISlider.js

import React from 'react';
import { useSelector, useDispatch } from 'react-redux';
import { setDpi } from '../slices/barcodeSlice';

const DPISlider = () => {
  const dispatch = useDispatch();
  const { dpi, isLimitExceeded } = useSelector((state) => state.barcode);

  const handleChange = (e) => {
    dispatch(setDpi(Number(e.target.value)));
  };

  return (
    <div>
      <label htmlFor="dpi-slider" className="block text-sm font-medium mb-1">
        DPI: {dpi}
      </label>
      <input
        id="dpi-slider"
        type="range"
        min="130"
        max="1000"
        step="1"
        value={dpi}
        onChange={handleChange}
        className="w-full"
        disabled={isLimitExceeded}
      />
      <div className="flex justify-between text-xs text-gray-500">
        <span>130</span>
        <span>1000</span>
      </div>
    </div>
  );
};

export default DPISlider;
