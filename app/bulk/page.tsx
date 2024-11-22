
'use client';

import React, { useState } from 'react';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import BulkWebOptions from '@/components/bulk/BulkWebOptions';

export default function BulkPage() {
  const [showWebOptions, setShowWebOptions] = useState(false);

  return (
    <div className="container mx-auto px-4 py-8">
      <h1 className="text-2xl font-bold mb-4">Generate Bulk Barcodes</h1>
      <p className="text-muted-foreground mb-8">
        Choose a method to bulk generate barcodes.
      </p>

      <div className="grid md:grid-cols-2 gap-6">
        {/* WEB Option */}
        <Card>
          <CardHeader>
            <CardTitle>Generate via Web</CardTitle>
            <CardDescription>Upload your data file to generate barcodes.</CardDescription>
          </CardHeader>
          <CardContent>
            <Button onClick={() => setShowWebOptions(true)}>Continue</Button>
            {showWebOptions && <BulkWebOptions />}
          </CardContent>
        </Card>

        {/* API Option */}
        <Card className="opacity-50 pointer-events-none">
          <CardHeader>
            <CardTitle>Generate via API</CardTitle>
            <CardDescription>Use our API to generate barcodes programmatically.</CardDescription>
          </CardHeader>
          <CardContent>
            <Button disabled>Under Development</Button>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}