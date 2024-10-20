// app/page.tsx

'use client';

import React, { useState, useEffect, useCallback } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { useMediaQuery } from 'react-responsive'
import { Loader2, Download, Copy, Printer } from 'lucide-react'

import { Input } from "@/components/ui/input"
import { Button } from "@/components/ui/button"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Slider } from "@/components/ui/slider"
import { Switch } from "@/components/ui/switch"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert"
import { useToast } from "@/components/ui/use-toast"

const apiDomain = process.env.NODE_ENV === 'development' ? 'http://localhost:8000' : 'https://thebarcodeapi.com';
const apiVersion = process.env.NEXT_PUBLIC_APP_VERSION || '0.1.5';

const barcodeTypes = [
  'code128', 'code39', 'ean', 'ean13', 'ean14', 'ean8', 'gs1', 'gs1_128',
  'gtin', 'isbn', 'isbn10', 'isbn13', 'issn', 'itf', 'jan', 'pzn', 'upc', 'upca'
];

const imageFormats = ['BMP', 'GIF', 'JPEG', 'PCX', 'PNG', 'TIFF']

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

export default function BarcodeGenerator() {
  const [barcodeType, setBarcodeType] = useState('code128')
  const [barcodeText, setBarcodeText] = useState('Change Me!')
  const [barcodeWidth, setBarcodeWidth] = useState(200)
  const [barcodeHeight, setBarcodeHeight] = useState(100)
  const [imageFormat, setImageFormat] = useState('PNG')
  const [showText, setShowText] = useState(true)
  const [isLoading, setIsLoading] = useState(false)
  const [barcodeUrl, setBarcodeUrl] = useState('')
  const [apiCallUrl, setApiCallUrl] = useState('')
  const [dpi, setDpi] = useState(300)
  const [error, setError] = useState(null)
  const [isLimitExceeded, setIsLimitExceeded] = useState(false)

  const isMobile = useMediaQuery({ maxWidth: 767 })
  const { toast } = useToast()

  const generateBarcode = useCallback(async (type, text, width, height, format, dpi, showText) => {
    setIsLoading(true)
    setError(null)
    const url = `${apiDomain}/api/generate?data=${encodeURIComponent(text)}&format=${type}&width=${width}&height=${height}&image_format=${format}&dpi=${dpi}&center_text=${showText}`
    console.log(url)
    try {
      const response = await fetch(url)
      if (!response.ok) {
        if (response.status === 429) {
          setIsLimitExceeded(true)
          throw new Error('Usage limit exceeded. Please try again tomorrow.')
        }
        throw new Error(`HTTP error! status: ${response.status}`)
      }
      const blob = await response.blob()
      const imageUrl = URL.createObjectURL(blob)
      setIsLoading(false)
      return imageUrl
    } catch (e) {
      setIsLoading(false)
      setError(e.message)
      return null
    }
  }, [])

  const debouncedUpdateBarcode = useCallback(
    debounce(async (type, text, width, height, format, dpi, showText) => {
      if (!isLimitExceeded) {
        const url = await generateBarcode(type, text, width, height, format, dpi, showText)
        if (url) {
          setBarcodeUrl(url)
          setApiCallUrl(`/api/generate?data=${encodeURIComponent(text)}&format=${type}&width=${width}&height=${height}&image_format=${format}&dpi=${dpi}&center_text=${showText}`)
        }
      }
    }, 250),
    [generateBarcode, isLimitExceeded]
  )

  useEffect(() => {
    debouncedUpdateBarcode(
      barcodeType,
      barcodeText,
      barcodeWidth,
      barcodeHeight,
      imageFormat,
      dpi,
      showText
    )
  }, [barcodeType, barcodeText, barcodeWidth, barcodeHeight, imageFormat, dpi, showText, debouncedUpdateBarcode])

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

  const handleTextChange = (e) => {
    const newText = e.target.value
    if (maxChars[barcodeType]) {
      setBarcodeText(newText.slice(0, maxChars[barcodeType]))
    } else {
      setBarcodeText(newText)
    }
  }

  const handleCopy = () => {
    // Append apiDomain to the URL
    const formattedAPiCallUrl = `${apiDomain}${apiCallUrl}`
    navigator.clipboard.writeText(formattedAPiCallUrl)
    toast({
      title: "Copied!",
      description: "API URL copied to clipboard",
    })
  }

  const handleDownload = () => {
    const cleanedBarcodeValue = cleanBarcodeValue(barcodeText)
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
        <Select value={barcodeType} onValueChange={setBarcodeType} disabled={isLimitExceeded}>
          <SelectTrigger>
            <SelectValue placeholder="Select barcode type" />
          </SelectTrigger>
          <SelectContent>
            {barcodeTypes.map(type => (
              <SelectItem key={type} value={type}>{type}</SelectItem>
            ))}
          </SelectContent>
        </Select>
      )
    } else {
      return (
        <div className="flex flex-wrap gap-2">
          {barcodeTypes.map(type => (
            <Button
              key={type}
              variant={barcodeType === type ? "default" : "outline"}
              size="sm"
              onClick={() => setBarcodeType(type)}
              disabled={isLimitExceeded}
            >
              {type}
            </Button>
          ))}
        </div>
      )
    }
  }

  const renderImageFormatInput = () => {
    if (isMobile) {
      return (
        <Select value={imageFormat} onValueChange={setImageFormat} disabled={isLimitExceeded}>
          <SelectTrigger>
            <SelectValue placeholder="Select image format" />
          </SelectTrigger>
          <SelectContent>
            {imageFormats.map(format => (
              <SelectItem key={format} value={format}>{format}</SelectItem>
            ))}
          </SelectContent>
        </Select>
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
    <div className="p-4 md:p-8 max-w-6xl mx-auto">
      <Card>
        <CardHeader>
          <CardTitle className="text-2xl font-bold text-center">
            The Barcode API {process.env.NODE_ENV === 'development' ? <span className="text-red-500">DEV v{apiVersion}*</span> : <span className="text-green-500">v{apiVersion}</span>}
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="grid md:grid-cols-2 gap-6">
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium mb-1">Barcode Type</label>
                {renderBarcodeTypeInput()}
              </div>
              <div>
                <label className="block text-sm font-medium mb-1">
                  Barcode Content {maxChars[barcodeType] ? `(Max ${maxChars[barcodeType]} characters)` : ''}
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
                  onValueChange={([value]) => setBarcodeWidth(value)}
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
                  onValueChange={([value]) => setBarcodeHeight(value)}
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
                  onValueChange={([value]) => setDpi(value)}
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
            <div className="space-y-4">
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
              <div className="mt-4 bg-gray-800 p-4 rounded-md relative">
                <h3 className="text-sm font-semibold mb-2 text-white">API Call:</h3>
                <div className="bg-gray-900 p-2 rounded">
                  <code className="text-xs text-white break-all">GET {apiCallUrl}</code>
                </div>
                <Button
                  size="icon"
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
                <Button variant="outline" className="flex-1">
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

function debounce(func, wait) {
  let timeout
  return function executedFunction(...args) {
    const later = () => {
      clearTimeout(timeout)
      func(...args)
    }
    clearTimeout(timeout)
    timeout = setTimeout(later, wait)
  }
}

const cleanBarcodeValue = (value) => {
  return value.replace(/[^a-zA-Z0-9]/g, '_');
};
