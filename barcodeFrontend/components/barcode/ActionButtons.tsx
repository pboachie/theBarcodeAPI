// ActionButtons.tsx
import React from 'react';
import { Copy, Download } from 'lucide-react';
import { Button } from "@/components/ui/button";
import { PrintButton } from "@/components/ui/print-button";

interface ActionButtonsProps {
  onCopy: () => void;
  onDownload: () => void;
  barcodeUrl: string;
}

export const ActionButtons: React.FC<ActionButtonsProps> = ({
  onCopy,
  onDownload,
  barcodeUrl
}) => {
  return (
    <div className="flex gap-2 additional-content flex-grow p-4">
      <Button onClick={onCopy} className="flex-1 bg-black text-white">
        <Copy className="w-4 h-4 mr-2" />
        Copy URL
      </Button>
      <Button onClick={onDownload} className="flex-1 bg-black text-white">
        <Download className="w-4 h-4 mr-2" />
        Download
      </Button>
      <PrintButton barcodeUrl={barcodeUrl} />
    </div>
  );
};
