'use client';

import React from 'react';
import { motion } from 'framer-motion';
import { Mail, Phone, MessageCircle, Clock, ArrowRight, FileText, Globe } from 'lucide-react';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import SupportForm from '@/components/support/SupportForm';

export function SupportPageClient() {
  const containerVariants = {
    hidden: { opacity: 0, y: 20 },
    visible: {
      opacity: 1,
      y: 0,
      transition: { duration: 0.6, ease: "easeOut" }
    }
  };

  const cardVariants = {
    hidden: { opacity: 0, scale: 0.95 },
    visible: {
      opacity: 1,
      scale: 1,
      transition: { duration: 0.4, ease: "easeOut" }
    }
  };

  return (
    <motion.div
      initial="hidden"
      animate="visible"
      variants={containerVariants}
      className="flex-1 bg-background px-4"
    >
      <div className="max-w-5xl mx-auto py-8 space-y-8">
        <div className="text-center space-y-2">
          <h1 className="text-2xl font-bold">theBarcodeAPI Support</h1>
          <p className="text-muted-foreground">
            Get expert assistance with barcode generation and API integration. Our support team is here to help you succeed.
          </p>
        </div>

        <motion.div variants={cardVariants} className="grid md:grid-cols-2 gap-6">
          <Card>
            <CardHeader className="pb-2">
              <CardTitle>Contact Us</CardTitle>
              <CardDescription>We&apos;ll get back to you within 24 hours</CardDescription>
            </CardHeader>
            <CardContent>
              <SupportForm />
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="pb-2">
              <CardTitle>Support Information</CardTitle>
              <CardDescription>Multiple ways to get help</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex items-center gap-3">
                <Mail className="text-primary h-5 w-5" />
                <div>
                  <h3 className="font-medium">Email Support</h3>
                  <p className="text-sm text-muted-foreground">support@thebarcodeapi.com</p>
                </div>
              </div>
              <div className="flex items-center gap-3">
                <Phone className="text-primary h-5 w-5" />
                <div>
                  <h3 className="font-medium">Phone Support</h3>
                  <p className="text-sm text-muted-foreground">+1 (XXX) XXX-XXXX</p>
                </div>
              </div>
              <div className="flex items-center gap-3">
                <MessageCircle className="text-primary h-5 w-5" />
                <div>
                  <h3 className="font-medium">Live Chat</h3>
                  <p className="text-sm text-muted-foreground">Available 24/7  <span style={{ color: 'red' }}>* (Under development)</span></p>
                </div>
              </div>
            </CardContent>
          </Card>
        </motion.div>

        <motion.div variants={cardVariants} className="grid md:grid-cols-3 gap-6">
          <div className="flex flex-col items-start gap-2">
            <Clock className="h-5 w-5 text-primary" />
            <h3 className="font-medium">24/7 Availability <span style={{ color: 'red' }}>* (Under development)</span></h3>
            <p className="text-sm text-muted-foreground">Round-the-clock support for all your barcode generation needs</p>
          </div>

          <div className="flex flex-col items-start gap-2">
            <ArrowRight className="h-5 w-5 text-primary" />
            <h3 className="font-medium">Quick Response  <span style={{ color: 'red' }}>* (Under development)</span></h3>
            <p className="text-sm text-muted-foreground">Fast and efficient support to keep your projects moving</p>
          </div>

          <div className="flex flex-col items-start gap-2">
            <FileText className="h-5 w-5 text-primary" />
            <h3 className="font-medium">Comprehensive Docs  <span style={{ color: 'red' }}>* (Coming soon)</span></h3>
            <p className="text-sm text-muted-foreground">Detailed documentation and integration guides</p>
          </div>
        </motion.div>

        <div className="grid grid-cols-2 gap-4 max-w-md mx-auto">
          <a href="https://api.thebarcodeapi.com/docs" target="_blank" rel="noopener noreferrer" className="flex items-center gap-2 text-sm hover:text-primary">
            <Globe className="h-4 w-4" />
            Documentation
          </a>
          <a href="/" className="flex items-center gap-2 text-sm hover:text-primary">
            <FileText className="h-4 w-4" />
            API Reference
          </a>
        </div>
      </div>
    </motion.div>
  );
}