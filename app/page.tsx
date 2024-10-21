// app/page.tsx

'use client';

import React, { useState, useEffect, useCallback, useRef } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { useMediaQuery } from 'react-responsive'
import { Loader2, Download, Copy, Printer } from 'lucide-react'

import { Input } from "@/components/ui/input"
import { Button } from "@/components/ui/button"
import { Slider } from "@/components/ui/slider"
import { Switch } from "@/components/ui/switch"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { useToast } from "@/components/ui/use-toast"
import { CustomSelect } from "@/components/ui/custom-select"

const apiDomain = process.env.NODE_ENV === 'development' ? 'http://localhost:8000' : 'https://thebarcodeapi.com';
import packageJson from '../package.json';

const apiVersion = packageJson.version || 'x.x.x';

const barcodeTypes = [
  'code128', 'code39', 'ean', 'ean13', 'ean14', 'ean8', 'gs1', 'gs1_128',
  'gtin', 'isbn', 'isbn10', 'isbn13', 'issn', 'itf', 'jan', 'pzn', 'upc', 'upca'
];

const imageFormats = ['BMP', 'GIF', 'JPEG', 'PNG'] // PCX, TIFF not supported via web

const maxChars = {
  ean13: 12,
  ean8: 7,
  ean14: 13,
  upca: 11,
  isbn10: 9,
  isbn13: 12,
  issn: 7,
  pzn: 6,
}

// Move generateBarcode outside the component
const generateBarcode = async (
  type: string,
  text: string | number | boolean,
  width: number,
  height: number,
  format: string,
  dpi: number,
  showText: boolean,
  setIsLoading: (isLoading: boolean) => void,
  setError: (error: string | null) => void,
  setIsLimitExceeded: (isExceeded: boolean) => void
): Promise<string | null> => {
  setIsLoading(true);
  setError(null);
  const url = `${apiDomain}/api/generate?data=${encodeURIComponent(text.toString())}&format=${type}&width=${width}&height=${height}&image_format=${format}&dpi=${dpi}&center_text=${showText}`;
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
    setIsLoading(false);
    return imageUrl;
  } catch (e) {
    setIsLoading(false);
    if (e instanceof Error) {
      setError(e.message);
    } else {
      setError('An unknown error occurred');
    }
    return null;
  }
};

export default function BarcodeGenerator() {
  const [barcodeType, setBarcodeType] = useState<keyof typeof maxChars | 'code128'>('code128')
  const [barcodeText, setBarcodeText] = useState('Change Me!')
  const [barcodeWidth, setBarcodeWidth] = useState(200)
  const [barcodeHeight, setBarcodeHeight] = useState(100)
  const [imageFormat, setImageFormat] = useState('PNG')
  const [showText, setShowText] = useState(true)
  const [isLoading, setIsLoading] = useState(false)
  const [barcodeUrl, setBarcodeUrl] = useState('')
  const [apiCallUrl, setApiCallUrl] = useState('')
  const [dpi, setDpi] = useState(300)
  const [error, setError] = useState<string | null>(null)
  const [isLimitExceeded, setIsLimitExceeded] = useState(false)

  const isMobile = useMediaQuery({ maxWidth: 767 })
  const { toast } = useToast()
  const timeoutRef = useRef<NodeJS.Timeout>();

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
    }, 250);
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
    const selectedItem = document.querySelector(`.select-item[aria-selected="true"]`);
    if (selectedItem) {
      selectedItem.setAttribute('aria-selected', 'false');
    }
    const newItem = document.querySelector(`.select-item[value="${barcodeType}"]`);
    if (newItem) {
      newItem.setAttribute('aria-selected', 'true');
    }
  }, [barcodeType]);

  useEffect(() => {
    setBarcodeText('')
    switch (barcodeType) {
      case 'ean13':
        setBarcodeText('5901234123457')
        break
      case 'ean8':
        setBarcodeText('96385074')
        break
      case 'ean14':
        setBarcodeText('01234567891234')
        break
      case 'upca':
        setBarcodeText('01234567890')
        break
      case 'isbn10':
        setBarcodeText('1234567890')
        break
      case 'isbn13':
        setBarcodeText('9781234567890')
        break
      case 'issn':
        setBarcodeText('9771234567003')
        break
      case 'pzn':
        setBarcodeText('1234567')
        break
      default:
        setBarcodeText('Change Me!')
    }
  }, [barcodeType])

  const handleTextChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const newText = e.target.value
    if (barcodeType in maxChars) {
      setBarcodeText(newText.slice(0, maxChars[barcodeType as keyof typeof maxChars]))
    } else {
      setBarcodeText(newText)
    }
  }

  const handleCopy = async () => {
    try {
      console.log("Copy button clicked")
      const formattedApiCallUrl = `${apiDomain}${apiCallUrl}`
      await navigator.clipboard.writeText(formattedApiCallUrl)
      toast({
        title: "Copied!",
        description: "API URL copied to clipboard",
        duration: 2200, // Display for 2.2 seconds
      })
    } catch (error) {
      console.error("Failed to copy:", error)
      toast({
        title: "Failed to Copy",
        description: "Could not copy the API URL to clipboard",
        variant: "destructive",
        duration: 3000,
      })
    }
  }

  const handleDownload = () => {
    const cleanedBarcodeValue = barcodeText.replace(/[^a-zA-Z0-9]/g, '')
    const fileName = `${cleanedBarcodeValue}_${barcodeWidth}_${barcodeHeight}.${imageFormat.toLowerCase()}`

    const link = document.createElement('a')
    link.href = barcodeUrl
    link.download = fileName
    document.body.appendChild(link)
    link.click()
    document.body.removeChild(link)
  }

  const renderBarcodeTypeInput = () => {
    if (isMobile) {
      return (
        <CustomSelect
        options={barcodeTypes.map(type => type.toUpperCase())}
        value={barcodeType.toUpperCase()}
        onChange={(value) => setBarcodeType(value.toLowerCase() as keyof typeof maxChars | 'code128')}
        placeholder="Select barcode type"
      />
      )
    } else {
      return (
        <div className="flex flex-wrap gap-2">
          {barcodeTypes.map(type => (
            <Button
              key={type}
              className={`barcode-type-button`}
              variant="outline"
              size="sm"
              onClick={() => setBarcodeType(type as keyof typeof maxChars | 'code128')}
              disabled={isLimitExceeded}
              data-state={barcodeType === type ? "active" : "inactive"}
            >
              {type.toUpperCase()}
            </Button>
          ))}
        </div>
      )
    }
  }

  const renderImageFormatInput = () => {
    if (isMobile) {
      return (
        <CustomSelect
          options={imageFormats}
          value={imageFormat}
          onChange={setImageFormat}
          placeholder="Select image format"
        />
      )
    } else {
      return (
        <div className="flex gap-2">
          {imageFormats.map(format => (
            <Button
              key={format}
              variant={imageFormat === format ? "default" : "outline"}
              size="sm"
              onClick={() => setImageFormat(format)}
              disabled={isLimitExceeded}
            >
              {format}
            </Button>
          ))}
        </div>
      )
    }
  }

  return (
    <div className="barcode-generator-container p-4 md:p-8">
      <Card className="max-w-full mx-auto">
        <CardHeader>
          <CardTitle className="text-2xl font-bold text-center">
            The Barcode API {process.env.NODE_ENV === 'development' ? <span className="text-red-500">DEV v{apiVersion}*</span> : <span className="text-green-500">v{apiVersion}</span>}
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex flex-col lg:flex-row gap-6">
            <div className="controls-area space-y-4 lg:w-1/3">
              <div>
                <label className="block text-sm font-medium mb-1">Barcode Type</label>
                {renderBarcodeTypeInput()}
              </div>
              <div>
                <label className="block text-sm font-medium mb-1">
                  Barcode Content {barcodeType in maxChars ? `(Max ${maxChars[barcodeType as keyof typeof maxChars]} characters)` : ''}
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
                  max={1000}
                  step={1}
                  value={[barcodeWidth]}
                  onValueChange={([value]: [number]) => setBarcodeWidth(value)}
                  disabled={isLimitExceeded}
                />
              </div>
              <div>
                <label className="block text-sm font-medium mb-1">Height: {barcodeHeight}px</label>
                <Slider
                  min={50}
                  max={1000}
                  step={1}
                  value={[barcodeHeight]}
                  onValueChange={([value]: [number]) => setBarcodeHeight(value)}
                  disabled={isLimitExceeded}
                />
              </div>
              <div>
                <label className="block text-sm font-medium mb-1">Image Format</label>
                {renderImageFormatInput()}
              </div>
              <div>
                <label className="block text-sm font-medium mb-1">DPI: {dpi}</label>
                <Slider
                  min={130}
                  max={1000}
                  step={1}
                  value={[dpi]}
                  onValueChange={([value]: [number]) => setDpi(value)}
                  disabled={isLimitExceeded}
                />
                <div className="flex justify-between text-xs text-gray-500">
                  <span>130</span>
                  <span>1000</span>
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
            <div className="preview-area space-y-4 lg:w-2/3">
              <div className="aspect-video bg-gray-100 rounded-lg flex items-center justify-center overflow-hidden">
                <AnimatePresence mode="wait">
                  {isLoading ? (
                    <motion.div
                      key="loader"
                      initial={{ opacity: 0 }}
                      animate={{ opacity: 1 }}
                      exit={{ opacity: 0 }}
                    >
                      <Loader2 className="w-8 h-8 animate-spin" />
                    </motion.div>
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
                    <motion.img
                      key="barcode"
                      src={barcodeUrl}
                      alt="Generated Barcode"
                      className="max-w-full max-h-full object-contain"
                      initial={{ opacity: 0, scale: 0.8 }}
                      animate={{ opacity: 1, scale: 1 }}
                      exit={{ opacity: 0, scale: 0.8 }}
                      transition={{ duration: 0.3 }}
                    />
                  )}
                </AnimatePresence>
              </div>
              <div className="bg-gray-800 p-4 rounded-md relative">
                <h3 className="text-sm font-semibold mb-2 text-white">API Call:</h3>
                <div className="bg-gray-900 p-2 rounded">
                  <code className="text-xs text-white break-all">GET {apiCallUrl}</code>
                </div>
                <Button
                  size="sm"
                  variant="ghost"
                  className="absolute top-2 right-2"
                  onClick={handleCopy}
                >
                  <Copy className="h-4 w-4 text-white" />
                </Button>
              </div>
              <div className="flex gap-2">
                <Button onClick={handleCopy} className="flex-1 bg-black text-white">
                  <Copy className="w-4 h-4 mr-2" />
                  Copy URL
                </Button>
                <Button onClick={handleDownload} className="flex-1 bg-black text-white">
                  <Download className="w-4 h-4 mr-2" />
                  Download
                </Button>
                <Button variant="outline" className="flex-1 bg-black text-white">
                  <Printer className="w-4 h-4 mr-2" />
                  Print
                </Button>
              </div>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  )
}