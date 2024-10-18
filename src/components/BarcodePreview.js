import React from 'react';
import { useSelector } from 'react-redux';
import { motion, AnimatePresence } from 'framer-motion';
import { Card, CardHeader, CardContent } from '@/components/ui/card';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Loader2 } from "lucide-react";

const BarcodePreview = () => {
  const { barcodeUrl, isLoading, error, apiCallUrl, rateLimit, isLimitExceeded } = useSelector(state => state.barcode);

  return (
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
          <h3 className="text-sm font-semibold mb-2">API Call:</h3>
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
  );
};

export default BarcodePreview;