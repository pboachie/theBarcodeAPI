// BarcodeControls.tsx

import React from 'react';
import { Input } from '@/components/ui/input';
import { Slider } from '@/components/ui/slider';
import { Switch } from '@/components/ui/switch';
import {
  BarcodeType,
  barcodeTypes,
  ImageFormat,
  imageFormats,
  maxChars,
} from '@/components/types/barcode';
import { FormatSelector } from './FormatSelector';
import { getBarcodeText } from './barcodeConfig';
import { Label } from '@radix-ui/react-dropdown-menu';

interface BarcodeControlsProps {
  barcodeType: BarcodeType;
  setBarcodeType: (type: BarcodeType) => void;
  barcodeText: string;
  setBarcodeText: (text: string) => void;
  barcodeWidth: number;
  setBarcodeWidth: React.Dispatch<React.SetStateAction<number>>;
  barcodeHeight: number;
  setBarcodeHeight: React.Dispatch<React.SetStateAction<number>>;
  imageFormat: ImageFormat;
  setImageFormat: (format: ImageFormat) => void;
  dpi: number;
  setDpi: (dpi: number) => void;
  showText: boolean;
  setShowText: (show: boolean) => void;
  customText: string;
  setCustomText: (text: string) => void;
  centerText: boolean;
  setCenterText: (center: boolean) => void;
  isLimitExceeded: boolean;
  className?: string;
}

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
  customText,
  setCustomText,
  centerText,
  setCenterText,
  isLimitExceeded,
  className,
}) => {
  const handleTextChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const newText = e.target.value;
    if (barcodeType in maxChars) {
      setBarcodeText(newText.slice(0, maxChars[barcodeType as keyof typeof maxChars]));
    } else {
      setBarcodeText(newText);
    }
  };

  const handleCustomTextChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setCustomText(e.target.value);
  };

  const handleTypeChange = (newType: BarcodeType) => {
    setBarcodeType(newType);
    setBarcodeText(getBarcodeText(newType));
  };

  const [maxDimension, setMaxDimension] = React.useState(600);
  const hasCalculatedMaxRef = React.useRef(false);
  const previousBreakpointRef = React.useRef<'mobile' | 'desktop'>(
    typeof window !== 'undefined' && window.innerWidth <= 768 ? 'mobile' : 'desktop'
  );

  React.useEffect(() => {
    const calculateAbsoluteMax = () => {
      const viewportWidth = window.innerWidth;
      const currentBreakpoint = viewportWidth <= 768 ? 'mobile' : 'desktop';

      if (!hasCalculatedMaxRef.current || previousBreakpointRef.current !== currentBreakpoint) {
        if (currentBreakpoint === 'mobile') {
          const container = document.querySelector('.barcode-container');
          if (container) {
            const containerRect = container.getBoundingClientRect();
            const mobileMax = Math.min(containerRect.width - 32, 300);
            setMaxDimension(Math.floor(mobileMax));
            setBarcodeWidth((prev) => Math.min(Number(prev), mobileMax));
            setBarcodeHeight((prev) => Math.min(Number(prev), mobileMax));
          }
        } else {
          const previewArea = document.querySelector('.preview-area');
          const container = document.querySelector('.barcode-container');
          if (previewArea && container) {
            const previewRect = previewArea.getBoundingClientRect();
            const containerRect = container.getBoundingClientRect();
            const maxSize = Math.min(
              Math.max(Math.min(previewRect.width, containerRect.width) * 0.8, 400),
              600
            );
            setMaxDimension(Math.floor(maxSize));
          }
        }

        previousBreakpointRef.current = currentBreakpoint;
        hasCalculatedMaxRef.current = true;
      }
    };

    const initialTimer = setTimeout(calculateAbsoluteMax, 100);

    const observer = new MutationObserver(() => {
      hasCalculatedMaxRef.current = false;
      calculateAbsoluteMax();
    });

    const container = document.querySelector('.barcode-container');
    if (container) {
      observer.observe(container, { attributes: true, childList: true, subtree: true });
    }

    const handleResize = () => {
      hasCalculatedMaxRef.current = false;
      calculateAbsoluteMax();
    };

    window.addEventListener('resize', handleResize);

    return () => {
      clearTimeout(initialTimer);
      observer.disconnect();
      window.removeEventListener('resize', handleResize);
    };
  }, [setBarcodeWidth, setBarcodeHeight]);

  return (
    <div className={`controls-area space-y-4 p-4 lg:w-1/4 flex-shrink-0 ${className}`}>
      <FormatSelector
        title="Barcode Type"
        options={barcodeTypes}
        value={barcodeType}
        onChange={handleTypeChange as (value: string) => void}
        disabled={isLimitExceeded}
      />

      <div>
        <Label className="text-sm font-medium mb-1">
          Barcode Content{' '}
          {barcodeType in maxChars
            ? `(Max ${maxChars[barcodeType as keyof typeof maxChars]} characters)`
            : ''}
        </Label>
        <Input
          value={barcodeText}
          onChange={handleTextChange}
          className="w-full"
          placeholder={`Enter ${barcodeType} content`}
          disabled={isLimitExceeded}
        />
      </div>

      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <Label className="text-sm font-medium">Show Text Below Barcode</Label>
          <Switch
            id="show-text"
            checked={showText}
            onCheckedChange={setShowText}
            disabled={isLimitExceeded}
          />
        </div>

        {showText && (
          <>
            <div className="flex items-center justify-between">
              <Label className="text-sm font-medium">Center Text</Label>
              <Switch
                id="center-text"
                checked={centerText}
                onCheckedChange={setCenterText}
                disabled={isLimitExceeded}
              />
            </div>

            <div className="space-y-2">
              <Label className="text-sm font-medium">Custom Text (Optional)</Label>
              <Input
                id="custom-text"
                value={customText}
                onChange={(e) => setCustomText(e.target.value)}
                className="w-full"
                placeholder="Enter custom text to display"
                disabled={isLimitExceeded}
              />
            </div>
          </>
        )}
      </div>

      <div>
        <Label className="text-sm font-medium mb-1">Width: {barcodeWidth}px</Label>
        <Slider
          min={50}
          max={maxDimension}
          step={1}
          value={[barcodeWidth]}
          onValueChange={([value]) => setBarcodeWidth(value)}
          disabled={isLimitExceeded}
        />
      </div>

      <div>
        <Label className="text-sm font-medium mb-1">Height: {barcodeHeight}px</Label>
        <Slider
          min={50}
          max={maxDimension}
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
        <Label className="text-sm font-medium mb-1">DPI: {dpi}</Label>
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
    </div>
  );
};
