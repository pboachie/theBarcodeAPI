// BarcodeGenerator.tsx

'use client';

import React, { useState, useEffect, useRef, useCallback } from 'react';
import { Card, CardHeader, CardContent, CardTitle } from '@/components/ui/card';
import { BarcodeControls } from './BarcodeControls';
import { BarcodeDisplay } from './BarcodeDisplay';
import { useToast } from '@/components/ui/use-toast';
import { BarcodeType, ImageFormat } from '@/components/types/barcode';
import { cleanupBarcodeUrl, generateBarcode } from './barcodeService';
import { ApiCallDisplay } from './ApiCallDisplay';
import { ActionButtons } from './ActionButtons';
import { getBarcodeText } from './barcodeConfig';

const apiDomain =
  process.env.NEXT_PUBLIC_API_DOMAIN ||
  (process.env.NODE_ENV === 'development' ? 'http://localhost:8000' : 'https://thebarcodeapi.com');

const BarcodeGenerator: React.FC = () => {
  const [barcodeType, setBarcodeType] = useState<BarcodeType>('code128');
  const [barcodeText, setBarcodeText] = useState('Change Me!');
  const [barcodeWidth, setBarcodeWidth] = useState(200);
  const [barcodeHeight, setBarcodeHeight] = useState(100);
  const [imageFormat, setImageFormat] = useState<ImageFormat>('PNG');
  const [isLoading, setIsLoading] = useState(false);
  const [barcodeUrl, setBarcodeUrl] = useState('');
  const [apiCallUrl, setApiCallUrl] = useState('');
  const [dpi, setDpi] = useState(200);
  const [error, setError] = useState<string | null>(null);
  const [isLimitExceeded, setIsLimitExceeded] = useState(false);
  const [showText, setShowText] = useState(true);
  const [customText, setCustomText] = useState('');
  const [centerText, setCenterText] = useState(true);

  const { toast } = useToast();
  const timeoutRef = useRef<NodeJS.Timeout>();

  const handleBarcodeTypeChange = (newType: BarcodeType) => setBarcodeType(newType);

  const handleCopy = async () => {
    try {
      const formattedApiCallUrl = `${apiDomain}${apiCallUrl}`;
      await navigator.clipboard.writeText(formattedApiCallUrl);
      toast({ title: 'Copied!', description: 'API URL copied to clipboard', duration: 2200 });
    } catch (error) {
      console.error('Failed to copy:', error);
      toast({
        title: 'Failed to Copy',
        description: 'Could not copy the API URL to clipboard',
        variant: 'destructive',
        duration: 3000,
      });
    }
  };

  const handleDownload = () => {
    const cleanedBarcodeValue = barcodeText.replace(/[^a-zA-Z0-9]/g, '');
    const fileName = `${cleanedBarcodeValue}_${barcodeWidth}_${barcodeHeight}.${imageFormat.toLowerCase()}`;
    const link = document.createElement('a');
    link.href = barcodeUrl;
    link.download = fileName;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  const debouncedUpdateBarcode = useCallback(
    (
      type: string,
      text: string,
      width: number,
      height: number,
      format: string,
      dpi: number,
      showText: boolean,
      customText: string,
      centerText: boolean
    ) => {
      if (timeoutRef.current) clearTimeout(timeoutRef.current);
      timeoutRef.current = setTimeout(async () => {
        if (!isLimitExceeded) {
          const displayText = getBarcodeText(type as BarcodeType, text);
          const url = await generateBarcode(
            type,
            displayText,
            width,
            height,
            format,
            dpi,
            showText,
            setIsLoading,
            setError,
            setIsLimitExceeded,
            customText,
            centerText
          );
          if (url) {
            setBarcodeUrl(url);
            const params = new URLSearchParams({
              data: encodeURIComponent(displayText),
              format: type,
              width: width.toString(),
              height: height.toString(),
              image_format: format,
              dpi: dpi.toString(),
              show_text: showText.toString(),
              center_text: centerText.toString(),
            });
            if (showText && customText)
              params.append('text_content', encodeURIComponent(customText));
            setApiCallUrl(`/api/generate?${params.toString()}`);
          }
        }
      }, 420);
    },
    [isLimitExceeded]
  );

  useEffect(() => {
    debouncedUpdateBarcode(
      barcodeType,
      barcodeText,
      barcodeWidth,
      barcodeHeight,
      imageFormat,
      dpi,
      showText,
      customText,
      centerText
    );
  }, [
    barcodeType,
    barcodeText,
    barcodeWidth,
    barcodeHeight,
    imageFormat,
    dpi,
    showText,
    customText,
    centerText,
    debouncedUpdateBarcode,
  ]);

  useEffect(() => {
    return () => {
      if (barcodeUrl) cleanupBarcodeUrl(barcodeUrl);
      if (timeoutRef.current) clearTimeout(timeoutRef.current);
    };
  }, [barcodeUrl]);

    return (
        <main className="container mx-auto">
            <div className="barcode-generator-container">
                <Card className="max-w-full">
                    <CardHeader>
                        <CardTitle className="text-2xl font-bold text-center relative">
                            <a href="/" className="absolute inset-0 z-10"></a>
                            The Barcode API {process.env.NODE_ENV == 'development' ? (
                                <span className="text-red-500">DEV*</span>
                            ) : (
                                <span className="text-green-500">*</span>
                            )}
                        </CardTitle>
                    </CardHeader>
                    <CardContent className="flex flex-col gap-6">
                        <div className="flex flex-col lg:flex-row gap-6">
                            <div className="order-1 lg:order-2 flex-1 flex justify-center items-center overflow-auto">
                                <BarcodeDisplay
                                    isLoading={isLoading}
                                    isLimitExceeded={isLimitExceeded}
                                    error={error}
                                    barcodeUrl={barcodeUrl}
                                />
                            </div>
                            {/* BarcodeControls appears second on mobile and first on desktop */}
                            <BarcodeControls
                                barcodeType={barcodeType}
                                setBarcodeType={handleBarcodeTypeChange}
                                barcodeText={barcodeText}
                                setBarcodeText={setBarcodeText}
                                barcodeWidth={barcodeWidth}
                                setBarcodeWidth={setBarcodeWidth}
                                barcodeHeight={barcodeHeight}
                                setBarcodeHeight={setBarcodeHeight}
                                imageFormat={imageFormat}
                                setImageFormat={setImageFormat}
                                dpi={dpi}
                                setDpi={setDpi}
                                showText={showText}
                                setShowText={setShowText}
                                customText={customText}
                                setCustomText={setCustomText}
                                centerText={centerText}
                                setCenterText={setCenterText}
                                isLimitExceeded={isLimitExceeded}
                                className="order-2 lg:order-1"
                            />
                        </div>

                        {/* API Call section */}
                        <div className="api-call-section order-last mt-6">
                            <div className="space-y-4">
                                <ApiCallDisplay
                                    apiCallUrl={apiCallUrl}
                                    onCopy={handleCopy}
                                />

                                <ActionButtons
                                    onCopy={handleCopy}
                                    onDownload={handleDownload}
                                    barcodeUrl={barcodeUrl}
                                />
                            </div>
                        </div>
                    </CardContent>
                </Card>
            </div>
        </main>
    );
};

export default BarcodeGenerator;