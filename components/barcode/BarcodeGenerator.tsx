// BarcodeGenerator.tsx

'use client';

import React, { useState, useEffect, useRef, useCallback } from 'react';
// import dynamic from 'next/dynamic';
import { Card, CardHeader, CardContent, CardTitle } from '@/components/ui/card';
import { BarcodeControls } from './BarcodeControls';
import { BarcodeDisplay } from './BarcodeDisplay';
import { useToast } from '@/components/ui/use-toast';
import packageJson from '../../package.json';
import { BarcodeType, ImageFormat } from './types';
import { cleanupBarcodeUrl, generateBarcode } from './barcodeService';
import { ApiCallDisplay } from './ApiCallDisplay';
import { ActionButtons } from './ActionButtons';

const apiDomain = process.env.NEXT_PUBLIC_API_DOMAIN ||
  (process.env.NODE_ENV === 'development' ? 'http://localhost:8000' : 'https://thebarcodeapi.com');

const apiVersion = packageJson.version || 'x.x.x';

const BarcodeGenerator: React.FC = () => {
    const [barcodeType, setBarcodeType] = useState<BarcodeType>('code128');
    const [barcodeText, setBarcodeText] = useState('Change Me!');
    const [barcodeWidth, setBarcodeWidth] = useState(200);
    const [barcodeHeight, setBarcodeHeight] = useState(100);
    const [imageFormat, setImageFormat] = useState<ImageFormat>('PNG');
    const [showText, setShowText] = useState(true);
    const [isLoading, setIsLoading] = useState(false);
    const [barcodeUrl, setBarcodeUrl] = useState('');
    const [apiCallUrl, setApiCallUrl] = useState('');
    const [dpi, setDpi] = useState(200);
    const [error, setError] = useState<string | null>(null);
    const [isLimitExceeded, setIsLimitExceeded] = useState(false);

    const { toast } = useToast();
    const timeoutRef = useRef<NodeJS.Timeout>();

    const handleBarcodeTypeChange = (newType: BarcodeType) => {
        setBarcodeType(newType);
    };

    const handleCopy = async () => {
        try {
            const formattedApiCallUrl = `${apiDomain}${apiCallUrl}`;
            await navigator.clipboard.writeText(formattedApiCallUrl);
            toast({
                title: "Copied!",
                description: "API URL copied to clipboard",
                duration: 2200,
            });
        } catch (error) {
            console.error("Failed to copy:", error);
            toast({
                title: "Failed to Copy",
                description: "Could not copy the API URL to clipboard",
                variant: "destructive",
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

    const debouncedUpdateBarcode = useCallback((
        type: string,
        text: string,
        width: number,
        height: number,
        format: string,
        dpi: number,
        showText: boolean
    ) => {
        if (timeoutRef.current) {
            clearTimeout(timeoutRef.current);
        }

        timeoutRef.current = setTimeout(async () => {
            if (!isLimitExceeded) {
                const url = await generateBarcode(
                    type,
                    text,
                    width,
                    height,
                    format,
                    dpi,
                    showText,
                    setIsLoading,
                    setError,
                    setIsLimitExceeded
                );
                if (url) {
                    setBarcodeUrl(url);
                    setApiCallUrl(`/api/generate?data=${encodeURIComponent(text)}&format=${type}&width=${width}&height=${height}&image_format=${format}&dpi=${dpi}&center_text=${showText}`);
                }
            }
        }, 740);
    }, [isLimitExceeded]);

    useEffect(() => {
        debouncedUpdateBarcode(
            barcodeType,
            barcodeText,
            barcodeWidth,
            barcodeHeight,
            imageFormat,
            dpi,
            showText
        );
    }, [barcodeType, barcodeText, barcodeWidth, barcodeHeight, imageFormat, dpi, showText, debouncedUpdateBarcode]);

    useEffect(() => {
        return () => {
            if (barcodeUrl) {
                cleanupBarcodeUrl(barcodeUrl);
            }
            if (timeoutRef.current) {
                clearTimeout(timeoutRef.current);
            }
        };
    }, [barcodeUrl]);

    return (
        <div className="barcode-generator-container p-4 md:p-8">
            <Card className="max-w-full mx-auto">
                <CardHeader>
                    <CardTitle className="text-2xl font-bold text-center">
                        The Barcode API {process.env.NODE_ENV === 'development' ?
                            <span className="text-red-500">DEV v{apiVersion}*</span> :
                            <span className="text-green-500">v{apiVersion}</span>
                        }
                    </CardTitle>
                </CardHeader>
                <CardContent>
                    <div className="flex flex-col lg:flex-row gap-6">
                        {/* BarcodeDisplay appears first on mobile and second on desktop */}
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
                            isLimitExceeded={isLimitExceeded}
                            className="order-2 lg:order-1"
                        />
                    </div>

                    <div className="barcode-display flex-1 flex justify-center items-center overflow-auto flex-grow">
                        <div className="preview-area space-y-4 lg:w-2/3">
                            {/* <BarcodeDisplay
                                isLoading={isLoading}
                                isLimitExceeded={isLimitExceeded}
                                error={error}
                                barcodeUrl={barcodeUrl}
                            /> */}

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
    );
};

export default BarcodeGenerator;