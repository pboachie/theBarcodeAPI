//src/components/ImageFormatSelect.js

import React from 'react';
import { useSelector, useDispatch } from 'react-redux';
import { setImageFormat } from '../slices/barcodeSlice';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '../components/ui/select';

const ImageFormatSelect = () => {
  const dispatch = useDispatch();
  const { imageFormat, isLimitExceeded } = useSelector((state) => state.barcode);

  const imageFormats = ['BMP', 'GIF', 'JPEG', 'PCX', 'PNG', 'TIFF'];

  const handleChange = (value) => {
    dispatch(setImageFormat(value));
  };

  return (
    <div>
      <label className="block text-sm font-medium mb-1">Image Format</label>
      <Select value={imageFormat} onValueChange={handleChange} disabled={isLimitExceeded}>
        <SelectTrigger className="w-full">
          <SelectValue placeholder="Select image format" />
        </SelectTrigger>
        <SelectContent>
          {imageFormats.map((format) => (
            <SelectItem key={format} value={format}>
              {format}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    </div>
  );
};

export default ImageFormatSelect;
