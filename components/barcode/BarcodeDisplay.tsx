// BarcodeDisplay.tsx

import React from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { Loader2 } from 'lucide-react';
import { Alert, AlertDescription, AlertTitle } from "@/components/ui/alert";

interface BarcodeDisplayProps {
  isLoading: boolean;
  isLimitExceeded: boolean;
  error: string | null;
  barcodeUrl: string;
}

export const BarcodeDisplay: React.FC<BarcodeDisplayProps> = ({
  isLoading,
  isLimitExceeded,
  error,
  barcodeUrl
}) => {
  return (
    <div className="barcode-container flex-grow max-w-full max-h-full p-4 aspect-video bg-gray-100 rounded-lg flex items-center justify-center overflow-auto">
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
            alt={`Generated barcode`}
            className="max-w-full max-h-full object-contain"
            initial={{ opacity: 0, scale: 0.8 }}
            animate={{ opacity: 1, scale: 1 }}
            exit={{ opacity: 0, scale: 0.8 }}
            transition={{ duration: 0.3 }}
          />
        )}
      </AnimatePresence>
    </div>
  );
};
