// BarcodeControls.tsx

import React, { useEffect } from 'react';
import { Input } from "@/components/ui/input";
import { Slider } from "@/components/ui/slider";
import { Switch } from "@/components/ui/switch";
import { BarcodeType, barcodeTypes, ImageFormat, imageFormats, maxChars } from './types';
import { FormatSelector } from './FormatSelector';

interface BarcodeControlsProps {
  barcodeType: BarcodeType;
  setBarcodeType: (type: BarcodeType) => void;
  barcodeText: string;
  setBarcodeText: (text: string) => void;
  barcodeWidth: number;
  setBarcodeWidth: (width: number) => void;
  barcodeHeight: number;
  setBarcodeHeight: (height: number) => void;
  imageFormat: ImageFormat;
  setImageFormat: (format: ImageFormat) => void;
  dpi: number;
  setDpi: (dpi: number) => void;
  showText: boolean;
  setShowText: (show: boolean) => void;
  isLimitExceeded: boolean;
}

const getDefaultBarcodeText = (type: BarcodeType): string => {
  switch (type) {
    case 'ean13':
      return '123456789123';
    case 'code39':
      return 'ABC 1234';
    case 'ean':
      return '5901234123457';
    case 'ean8':
      return '1234567';
    case 'jan':
      return '453456999999';
    case 'itf':
      return '01234567890123';
    case 'ean14':
      return '1234567890123';
    case 'upc':
      return '12345678901';
    case 'upca':
      return '01234567890';
    case 'isbn':
      return '9781234567890';
    case 'isbn10':
      return '123456789';
    case 'isbn13':
      return '978123456789';
    case 'gs1_128':
      return '0101234567890128BAR-IT';
    case 'gtin':
      return '01234567890128';
    case 'issn':
      return '1234567';
    case 'pzn':
      return '123456';
    default:
      return 'Change Me!';
  }
};

export const BarcodeControls: React.FC<BarcodeControlsProps> = ({
  barcodeType,
  setBarcodeType,
  barcodeText,
  setBarcodeText,
  barcodeWidth,
  setBarcodeWidth,
  barcodeHeight,
  setBarcodeHeight,
  imageFormat,
  setImageFormat,
  dpi,
  setDpi,
  showText,
  setShowText,
  isLimitExceeded
}) => {
  const handleTextChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const newText = e.target.value;
    if (barcodeType in maxChars) {
      setBarcodeText(newText.slice(0, maxChars[barcodeType as keyof typeof maxChars]));
    } else {
      setBarcodeText(newText);
    }
  };

  const handleTypeChange = (newType: BarcodeType) => {
    setBarcodeType(newType);
    setBarcodeText(getDefaultBarcodeText(newType));
  };

  // Set initial default text if empty
  useEffect(() => {
    if (!barcodeText) {
      setBarcodeText(getDefaultBarcodeText(barcodeType));
    }
  }, [barcodeText, barcodeType, setBarcodeText]);

  return (
    <div className="controls-area space-y-4 lg:w-1/4 flex-shrink-0">
      <FormatSelector
        title="Barcode Type"
        options={barcodeTypes}
        value={barcodeType}
        onChange={handleTypeChange as (value: string) => void}
        disabled={isLimitExceeded}
      />

      <div>
        <label className="block text-sm font-medium mb-1">
          Barcode Content {barcodeType in maxChars ?
            `(Max ${maxChars[barcodeType as keyof typeof maxChars]} characters)` :
            ''
          }
        </label>
        <Input
          value={barcodeText}
          onChange={handleTextChange}
          className="w-full"
          placeholder={`Enter ${barcodeType} content`}
          disabled={isLimitExceeded}
        />
      </div>

      <div>
        <label className="block text-sm font-medium mb-1">Width: {barcodeWidth}px</label>
        <Slider
          min={50}
          max={600}
          step={1}
          value={[barcodeWidth]}
          onValueChange={([value]) => setBarcodeWidth(value)}
          disabled={isLimitExceeded}
        />
      </div>

      <div>
        <label className="block text-sm font-medium mb-1">Height: {barcodeHeight}px</label>
        <Slider
          min={50}
          max={600}
          step={1}
          value={[barcodeHeight]}
          onValueChange={([value]) => setBarcodeHeight(value)}
          disabled={isLimitExceeded}
        />
      </div>

      <FormatSelector
        title="Image Format"
        options={imageFormats}
        value={imageFormat}
        onChange={setImageFormat as (value: string) => void}
        disabled={isLimitExceeded}
      />

      <div>
        <label className="block text-sm font-medium mb-1">DPI: {dpi}</label>
        <Slider
          min={130}
          max={600}
          step={1}
          value={[dpi]}
          onValueChange={([value]) => setDpi(value)}
          disabled={isLimitExceeded}
        />
        <div className="flex justify-between text-xs text-gray-500">
          <span>130</span>
          <span>600</span>
        </div>
      </div>

      <div className="flex items-center space-x-2">
        <Switch
          id="show-text"
          checked={showText}
          onCheckedChange={setShowText}
          disabled={isLimitExceeded}
        />
        <label htmlFor="show-text" className="text-sm font-medium">
          Center Text in Barcode
        </label>
      </div>
    </div>
  );
};
