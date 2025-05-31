
'use client';

import React, { useState } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Upload } from 'lucide-react';

export default function BulkWebOptions() {
  const [file, setFile] = useState<File | null>(null);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files?.[0]) {
      setFile(e.target.files[0]);
    }
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    // Process the uploaded file
  };

  return (
    <form onSubmit={handleSubmit} className="mt-6 space-y-4">
      <div>
        <Label htmlFor="file">Upload File</Label>
        <Input
          type="file"
          id="file"
          accept=".csv, .xlsx, .xls, .txt"
          onChange={handleFileChange}
          required
        />
        <p className="text-sm text-muted-foreground mt-2">
          Supported formats: CSV, Excel, TXT. The file should contain a <code>data</code> column and an optional <code>filename</code> column.
        </p>
      </div>
      <Button type="submit" disabled={!file}>
        <Upload className="mr-2 h-4 w-4" />
        Generate Barcodes
      </Button>
    </form>
  );
}