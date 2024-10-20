// src/components/BarcodeDemo.js

import React, { useState, useEffect, useCallback } from 'react';
import { motion, AnimatePresence, color } from 'framer-motion';
import { Input } from '../components/ui/input';
import { Card, CardHeader, CardContent } from '../components/ui/card';
import { Loader2 } from 'lucide-react';
import { Alert, AlertDescription, AlertTitle } from '../components/ui/alert';

const BarcodeDemo = () => {
  const [barcodeType, setBarcodeType] = useState('code128');
  const [barcodeText, setBarcodeText] = useState('Change Me!');
  const [barcodeWidth, setBarcodeWidth] = useState(200);
  const [barcodeHeight, setBarcodeHeight] = useState(100);
  const [showText, setShowText] = useState(true);
  const [barcodeUrl, setBarcodeUrl] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [apiCallUrl, setApiCallUrl] = useState('');
  const [imageFormat, setImageFormat] = useState('PNG');
  const [dpi, setDpi] = useState(300);
  const [error, setError] = useState(null);
  const [rateLimit, setRateLimit] = useState({
    requests: 0,
    remaining: 0,
    reset: 0,
  });
  const [isLimitExceeded, setIsLimitExceeded] = useState(false);

  const barcodeTypes = [
    'code128',
    'code39',
    'ean',
    'ean13',
    'ean14',
    'ean8',
    'gs1',
    'gs1_128',
    'gtin',
    'isbn',
    'isbn10',
    'isbn13',
    'issn',
    'itf',
    'jan',
    'pzn',
    'upc',
    'upca',
  ];

  const imageFormats = ['BMP', 'GIF', 'JPEG', 'PCX', 'PNG', 'TIFF'];

  const maxChars = {
    ean13: 12,
    ean8: 7,
    ean14: 13,
    upca: 11,
    isbn10: 9,
    isbn13: 12,
    issn: 7,
    pzn: 6,
  };

  const generateBarcode = useCallback(async (type, text, width, height, format, dpi, showText) => {
    setIsLoading(true);
    setError(null);
    const url = `http://localhost:8000/barcode/generate?data=${encodeURIComponent(
      text
    )}&format=${type}&width=${width}&height=${height}&image_format=${format}&dpi=${dpi}&center_text=${showText}`;
    try {
      const response = await fetch(url);
      if (!response.ok) {
        if (response.status === 429) {
          setIsLimitExceeded(true);
          throw new Error('Usage limit exceeded. Please try again tomorrow.');
        }
        throw new Error(`HTTP error! status: ${response.status}`);
      }
      const blob = await response.blob();
      const imageUrl = URL.createObjectURL(blob);
      setRateLimit({
        requests: response.headers.get('X-Rate-Limit-Requests'),
        remaining: response.headers.get('X-Rate-Limit-Remaining'),
        reset: response.headers.get('X-Rate-Limit-Reset'),
      });
      setIsLoading(false);
      return imageUrl;
    } catch (e) {
      setIsLoading(false);
      setError(e.message);
      return null;
    }
  }, []);

  const debouncedUpdateBarcode = useCallback(
    debounce(async (type, text, width, height, format, dpi, showText) => {
      if (!isLimitExceeded) {
        const url = await generateBarcode(type, text, width, height, format, dpi, showText);
        if (url) {
          setBarcodeUrl(url);
          setApiCallUrl(
            `/api/barcode/generate?data=${encodeURIComponent(
              text
            )}&format=${type}&width=${width}&height=${height}&image_format=${format}&dpi=${dpi}&center_text=${showText}`
          );
        }
      }
    }, 250),
    [generateBarcode, isLimitExceeded]
  );

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
  }, [
    barcodeType,
    barcodeText,
    barcodeWidth,
    barcodeHeight,
    imageFormat,
    dpi,
    showText,
    debouncedUpdateBarcode,
  ]);

  useEffect(() => {
    setBarcodeText('');
    // Set select to barcodeContent
    switch (barcodeType) {
      case 'ean13':
        setBarcodeText('5901234123457');
        break;
      case 'ean8':
        setBarcodeText('96385074');
        break;
      case 'ean14':
        setBarcodeText('01234567891234');
        break;
      case 'upca':
        setBarcodeText('01234567890');
        break;
      case 'isbn10':
        setBarcodeText('1234567890');
        break;
      case 'isbn13':
        setBarcodeText('9781234567890');
        break;
      case 'issn':
        setBarcodeText('9771234567003');
        break;
      case 'pzn':
        setBarcodeText('1234567');
        break;
      default:
        setBarcodeText('Change Me!');
    }
  }, [barcodeType]);

  const handleTextChange = (e) => {
    const newText = e.target.value;
    if (maxChars[barcodeType]) {
      setBarcodeText(newText.slice(0, maxChars[barcodeType]));
    } else {
      setBarcodeText(newText);
    }
  };

  return (
    <div className="p-4 md:p-8 max-w-6xl mx-auto bg-cream text-slate-800">
      <h1 className="text-3xl font-bold mb-6 text-center">
        The Barcode Api {process.env.NODE_ENV === 'development' ? <span style={{ color: 'red' }}>DEV*</span> : '®'}
      </h1>
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
        <Card className={`bg-white shadow-lg ${isLimitExceeded ? 'opacity-50' : ''}`}>
          <CardHeader>
            <h2 className="text-xl font-semibold">Barcode Configuration</h2>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium mb-1">Barcode Type</label>
                <select
                  value={barcodeType}
                  onChange={(e) => setBarcodeType(e.target.value)}
                  disabled={isLimitExceeded}
                  className="w-full p-2 border rounded"
                >
                  {barcodeTypes.map((type) => (
                    <option key={type} value={type}>
                      {type}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium mb-1">
                  Barcode Content{' '}
                  {maxChars[barcodeType] ? `(Max ${maxChars[barcodeType]} characters)` : ''}
                </label>
                <Input
                  value={barcodeText}
                  onChange={(e) => handleTextChange(e)}
                  onFocus={(e) => {
                    const value = e.target.value;
                    e.target.value = '';
                    e.target.value = value;
                  }}
                  className="w-full"
                  placeholder={`Enter ${barcodeType} content`}
                  disabled={isLimitExceeded}
                />
              </div>
              <div>
                <label className="block text-sm font-medium mb-1">Width: {barcodeWidth}px</label>
                <input
                  type="range"
                  min={50}
                  max={1000}
                  step={1}
                  value={barcodeWidth}
                  onChange={(e) => setBarcodeWidth(Number(e.target.value))}
                  className="w-full"
                  disabled={isLimitExceeded}
                />
              </div>
              <div>
                <label className="block text-sm font-medium mb-1">Height: {barcodeHeight}px</label>
                <input
                  type="range"
                  min={50}
                  max={1000}
                  step={1}
                  value={barcodeHeight}
                  onChange={(e) => setBarcodeHeight(Number(e.target.value))}
                  className="w-full"
                  disabled={isLimitExceeded}
                />
              </div>
              <div>
                <label className="block text-sm font-medium mb-1">Image Format</label>
                <select
                  value={imageFormat}
                  onChange={(e) => setImageFormat(e.target.value)}
                  disabled={isLimitExceeded}
                  className="w-full p-2 border rounded"
                >
                  {imageFormats.map((format) => (
                    <option key={format} value={format}>
                      {format}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium mb-1">DPI: {dpi}</label>
                <input
                  type="range"
                  min={130}
                  max={1000}
                  step={1}
                  value={dpi}
                  onChange={(e) => setDpi(Number(e.target.value))}
                  className="w-full"
                  disabled={isLimitExceeded}
                />
                <div className="flex justify-between text-xs text-gray-500">
                  <span>130</span>
                  <span>1000</span>
                </div>
              </div>
              <div className="flex items-center">
                <input
                  type="checkbox"
                  checked={showText}
                  onChange={(e) => setShowText(e.target.checked)}
                  id="show-text"
                  className="mr-2 h-4 w-4"
                  disabled={isLimitExceeded}
                />
                <label htmlFor="show-text" className="text-sm font-medium">
                  Center Text in Barcode
                </label>
              </div>
            </div>
          </CardContent>
        </Card>
        <Card className="bg-white shadow-lg">
          <CardHeader>
            <h2 className="text-xl font-semibold">Barcode Preview</h2>
          </CardHeader>
          <CardContent>
            <div className="flex justify-center items-center h-[400px] overflow-hidden">
              {isLoading ? (
                <Loader2 className="h-8 w-8 animate-spin" />
              ) : isLimitExceeded ? (
                <Alert variant="destructive">
                  <AlertTitle>Usage Limit Exceeded</AlertTitle>
                  <AlertDescription>Please try again tomorrow.</AlertDescription>
                </Alert>
              ) : error ? (
                <Alert variant="destructive">
                  <AlertTitle>Error</AlertTitle>
                  <AlertDescription>{error}</AlertDescription>
                </Alert>
              ) : (
                <AnimatePresence mode="wait">
                  <motion.div
                    key={barcodeUrl}
                    initial={{ opacity: 0, scale: 0.8 }}
                    animate={{ opacity: 1, scale: 1 }}
                    exit={{ opacity: 0, scale: 0.8 }}
                    transition={{ duration: 0.3 }}
                    className="flex flex-col items-center justify-center"
                  >
                    <img
                      src={barcodeUrl}
                      alt="Generated Barcode"
                      className="max-w-full max-h-full object-contain"
                    />
                  </motion.div>
                </AnimatePresence>
              )}
            </div>
            <div className="mt-4 bg-slate-100 p-4 rounded-md">
              <h3 className="text-sm font-semibold mb-2">API Call:</h3>
              <code className="text-xs break-all">GET {apiCallUrl}</code>
            </div>
            {/* <div className="mt-4 bg-slate-100 p-4 rounded-md">
              <h3 className="text-sm font-semibold mb-2">Rate Limit Info:</h3>
              <p className="text-xs">Requests: {rateLimit.requests}</p>
              <p className="text-xs">Remaining: {rateLimit.remaining}</p>
              <p className="text-xs">
                Reset:{' '}
                {new Date(
                  Date.now() + rateLimit.reset * 1000
                ).toLocaleString()}
              </p>
            </div> */}
          </CardContent>
        </Card>
      </div>
    </div>
  );
};

// Debounce function
function debounce(func, wait) {
  let timeout;
  return function executedFunction(...args) {
    const later = () => {
      clearTimeout(timeout);
      func(...args);
    };
    clearTimeout(timeout);
    timeout = setTimeout(later, wait);
  };
}

export default BarcodeDemo;
