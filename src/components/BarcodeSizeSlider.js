import React from 'react';
import PropTypes from 'prop-types';
import { useSelector, useDispatch } from 'react-redux';
import { Slider } from '../components/ui/slider';
import { setBarcodeWidth, setBarcodeHeight } from '../slices/barcodeSlice';

const BarcodeSizeSlider = ({ type }) => {
  const dispatch = useDispatch();
  const { barcodeWidth, barcodeHeight, isLimitExceeded } = useSelector((state) => state.barcode);

  const value = type === 'width' ? barcodeWidth : barcodeHeight;
  const setAction = type === 'width' ? setBarcodeWidth : setBarcodeHeight;

  const handleChange = (newValue) => {
    dispatch(setAction(newValue));
  };

  return (
    <div>
      <label className="block text-sm font-medium mb-1">
        {`${type.charAt(0).toUpperCase() + type.slice(1)}: ${value}px`}
      </label>
      <Slider
        min={50}
        max={1000}
        step={1}
        value={value}
        onValueChange={handleChange}
        className="w-full"
        disabled={isLimitExceeded}
      />
    </div>
  );
};

BarcodeSizeSlider.propTypes = {
  type: PropTypes.string.isRequired,
};

export default BarcodeSizeSlider;
