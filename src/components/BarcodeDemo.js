// src/components/BarcodeDemo.js

import { Input } from '../components/ui/input';
import { Slider } from '../components/ui/slider';
import { Switch } from '../components/ui/switch';
import { Card, CardHeader, CardContent } from '../components/ui/card';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "../components/ui/select";
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
    reset: 0
  });
  const [isLimitExceeded, setIsLimitExceeded] = useState(false);

  const imageFormats = ['BMP', 'GIF', 'JPEG', 'PCX', 'PNG', 'TIFF'];

  const generateBarcode = useCallback(async (type, text, width, height, format, dpi, showText) => {
    setIsLoading(true);
    setError(null);
    const url = `/api/barcode/generate?data=${encodeURIComponent(text)}&format=${type}&width=${width}&height=${height}&image_format=${format}&dpi=${dpi}¢er_text=${showText}`;
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
        reset: response.headers.get('X-Rate-Limit-Reset')
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
          setApiCallUrl(`/api/barcode/generate?data=${encodeURIComponent(text)}&format=${type}&width=${width}&height=${height}&image_format=${format}&dpi=${dpi}¢er_text=${showText}`);
        }
      }
    }, 250),
    [generateBarcode, isLimitExceeded]
  );

  useEffect(() => {
    debouncedUpdateBarcode(barcodeType, barcodeText, barcodeWidth, barcodeHeight, imageFormat, dpi, showText);
  }, [barcodeType, barcodeText, barcodeWidth, barcodeHeight, imageFormat, dpi, showText, debouncedUpdateBarcode]);

  return (
    <div className="p-4 md:p-8 max-w-6xl mx-auto bg-cream text-slate-800">
      <h1 className="text-3xl font-bold mb-6 text-center">TheBarcodeAPI</h1>
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
        <Card className={`bg-white shadow-lg ${isLimitExceeded ? 'opacity-50' : ''}`}>
          <CardHeader>
            <h2 className="text-xl font-semibold">Barcode Configuration</h2>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium mb-1">Barcode Type</label>
                <Select value={barcodeType} onValueChange={setBarcodeType} disabled={isLimitExceeded}>
                  <SelectTrigger className="w-full">
                    <SelectValue placeholder="Select barcode type" />
                  </SelectTrigger>
                  <SelectContent>
                    {isLoading ? (
                      <div>Loading...</div>
                    ) : (
                      barcodeTypes && barcodeTypes.map((type) => (
                        <SelectItem key={type} value={type}>{type}</SelectItem>
                      ))
                    )}
                  </SelectContent>
                </Select>
              </div>
              <div>
                <label className="block text-sm font-medium mb-1">Barcode Content</label>
                <Input
                  value={barcodeText}
                  onChange={(e) => setBarcodeText(e.target.value)}
                  className="w-full"
                  placeholder="Enter barcode content"
                  disabled={isLimitExceeded}
                />
              </div>
              <div>
                <label className="block text-sm font-medium mb-1">Width: {barcodeWidth}px</label>
                <Slider
                  min={50}
                  max={1000}
                  step={1}
                  value={barcodeWidth}
                  onValueChange={(value) => setBarcodeWidth(value)}
                  className="w-full"
                  disabled={isLimitExceeded}
                />
              </div>

              <div>
                <label className="block text-sm font-medium mb-1">Image Format</label>
                <Select value={imageFormat} onValueChange={setImageFormat} disabled={isLimitExceeded}>
                  <SelectTrigger className="w-full">
                    <SelectValue placeholder="Select image format" />
                  </SelectTrigger>
                  <SelectContent>
                    {imageFormats && imageFormats.map((format) => (
                      <SelectItem key={format} value={format}>{format}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <div>
                <label className="block text-sm font-medium mb-1">DPI: {dpi}</label>
                <Slider
                  min={130}
                  max={1000}
                  step={1}
                  value={dpi}
                  onValueChange={(value) => setDpi(value)}
                  className="w-full"
                  disabled={isLimitExceeded}
                />
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
                    <img src={barcodeUrl} alt="Generated Barcode" className="max-w-full max-h-full object-contain" />
                  </motion.div>
                </AnimatePresence>
              )}
            </div>
            <div className="mt-4 bg-slate-100 p-4 rounded-md">
              <h3 className="text-sm font-semibold mb-2">Try Me:</h3>
              <code className="text-xs break-all">
                GET {apiCallUrl}
              </code>
            </div>
            <div className="mt-4 bg-slate-100 p-4 rounded-md">
              <h3 className="text-sm font-semibold mb-2">Rate Limit Info:</h3>
              <p className="text-xs">Requests: {rateLimit.requests}</p>
              <p className="text-xs">Remaining: {rateLimit.remaining}</p>
              <p className="text-xs">Reset: {new Date(Date.now() + rateLimit.reset * 1000).toLocaleString()}</p>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
};

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
import { motion, AnimatePresence } from 'framer-motion';
import React, { useState, useCallback, useEffect, barcodeTypes } from 'react';

import { Loader2 } from 'lucide-react';
