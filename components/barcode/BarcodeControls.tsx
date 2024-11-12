// BarcodeControls.tsx

import React from 'react';
import { Input } from "@/components/ui/input";
import { Slider } from "@/components/ui/slider";
import { Switch } from "@/components/ui/switch";
import { BarcodeType, barcodeTypes, ImageFormat, imageFormats, maxChars } from '@/components/types/barcode';
import { FormatSelector } from './FormatSelector';
import { getBarcodeText } from './barcodeConfig';

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

  const handleTypeChange = (newType: BarcodeType) => {
    setBarcodeType(newType);
    setBarcodeText(getBarcodeText(newType)); // Updated usage
  };

  const [maxDimension, setMaxDimension] = React.useState(600);
  const hasCalculatedMaxRef = React.useRef(false);
  const previousBreakpointRef = React.useRef<'mobile' | 'desktop'>(
    window.innerWidth <= 768 ? 'mobile' : 'desktop'
  );

  React.useEffect(() => {
    const calculateAbsoluteMax = () => {
      const viewportWidth = window.innerWidth;
      const currentBreakpoint = viewportWidth <= 768 ? 'mobile' : 'desktop';

      // Force recalculation on breakpoint change
      if (!hasCalculatedMaxRef.current || previousBreakpointRef.current !== currentBreakpoint) {
        if (currentBreakpoint === 'mobile') {
          // For mobile: Calculate based on viewport and container constraints
          const container = document.querySelector('.barcode-container');
          if (container) {
            const containerRect = container.getBoundingClientRect();
            const mobileMax = Math.min(
              containerRect.width - 32, // Account for padding
              300 // Hard cap for mobile
            );
            setMaxDimension(Math.floor(mobileMax));
            setBarcodeWidth((prev) => Math.min(Number(prev), mobileMax));
            setBarcodeHeight((prev) => Math.min(Number(prev), mobileMax));

          }
        } else {
          // Desktop calculation remains the same
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

    // Run initial calculation after a short delay to ensure DOM is ready
    const initialTimer = setTimeout(calculateAbsoluteMax, 100);

    // Set up mutation observer to watch for container size changes
    const observer = new MutationObserver(() => {
      hasCalculatedMaxRef.current = false;
      calculateAbsoluteMax();
    });

    const container = document.querySelector('.barcode-container');
    if (container) {
      observer.observe(container, { attributes: true, childList: true, subtree: true });
    }

    // Handle resize events
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
          max={maxDimension}
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
