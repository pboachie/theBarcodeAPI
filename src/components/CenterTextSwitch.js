//src/components/CenterTextSwitch.js

import React from 'react';
import { useSelector, useDispatch } from 'react-redux';
import { setShowText } from '../slices/barcodeSlice';

const CenterTextSwitch = () => {
  const dispatch = useDispatch();
  const { showText, isLimitExceeded } = useSelector((state) => state.barcode);

  const handleChange = (e) => {
    dispatch(setShowText(e.target.checked));
  };

  return (
    <div className="flex items-center">
      <input
        type="checkbox"
        id="center-text"
        checked={showText}
        onChange={handleChange}
        disabled={isLimitExceeded}
        className="mr-2 h-4 w-4"
      />
      <label htmlFor="center-text" className="text-sm font-medium">
        Center Text in Barcode
      </label>
    </div>
  );
};

export default CenterTextSwitch;
