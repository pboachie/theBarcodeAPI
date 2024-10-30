// ApiCallDisplay.tsx

import React from 'react';
import { Copy } from 'lucide-react';
import { Button } from "@/components/ui/button";
import { useToast } from "@/components/ui/use-toast";

interface ApiCallDisplayProps {
  apiCallUrl: string;
  onCopy: () => void;
}

export const ApiCallDisplay: React.FC<ApiCallDisplayProps> = ({
  apiCallUrl,
  onCopy
}) => {
  return (
    <div className="bg-gray-800 p-4 rounded-md relative api-call-area">
      <h3 className="text-sm font-semibold mb-2 text-white">API Call:</h3>
      <div className="bg-gray-900 p-2 rounded">
        <code className="text-xs text-white break-all">GET {apiCallUrl}</code>
      </div>
      <Button
        size="sm"
        variant="ghost"
        className="absolute top-2 right-2"
        onClick={onCopy}
      >
        <Copy className="h-4 w-4 text-white" />
      </Button>
    </div>
  );
};
