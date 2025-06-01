'use client';

import React, { useState } from 'react';
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '@/components/ui/card';
import { motion, AnimatePresence } from 'framer-motion';
import { useToast } from '@/components/ui/use-toast';
import BulkWebOptions from '@/components/bulk/BulkWebOptions';
import { AlertCircle } from 'lucide-react';

export default function BulkPage() {
    const [showWebOptions, setShowWebOptions] = useState(false); // Modified to allow setting
    const { toast } = useToast();

    const handleAPIClick = () => {
        toast({
            title: "Feature Under Development",
            description: "The API bulk generation feature is coming soon. Please check back later!",
            variant: "default",
            duration: 3000,
        });
    };

    // Removed handleWebClick function

    const containerVariants = {
        hidden: { opacity: 0, y: 20 },
        visible: {
            opacity: 1,
            y: 0,
            transition: { duration: 0.6, ease: "easeOut" }
        }
    };

    const optionsVariants = {
        hidden: { opacity: 0, height: 0 },
        visible: {
            opacity: 1,
            height: "auto",
            transition: { duration: 0.3, ease: "easeInOut" }
        }
    };

    return (
        <motion.div
            initial="hidden"
            animate="visible"
            variants={containerVariants}
            className="container mx-auto px-4 py-8"
        >
            <h1 className="text-2xl font-bold mb-4">Generate Bulk Barcodes</h1>
            <p className="text-muted-foreground mb-8">
                Choose a method to bulk generate barcodes.
            </p>

            <div className="grid md:grid-cols-2 gap-6">
                {/* WEB Option */}
                <motion.div
                    whileHover={{ scale: 1.02 }}
                    whileTap={{ scale: 0.98 }}
                    transition={{ type: "spring", stiffness: 400, damping: 17 }}
                >
                    <Card
                        className="cursor-pointer hover:opacity-90 transition-opacity relative overflow-hidden" // Removed opacity-75 to make it look enabled
                        onClick={() => setShowWebOptions(prev => !prev)} // Modified onClick handler
                    >
                        <CardHeader>
                            <CardTitle className="flex items-center gap-2">
                                Generate via Web
                                {/* <AlertCircle className="h-4 w-4 text-yellow-500" /> Re-enable if still conditionally disabled */}
                            </CardTitle>
                            <CardDescription>Upload your data file to generate barcodes.</CardDescription>
                        </CardHeader>
                        {/* Removed the overlay div to make it look enabled */}
                    </Card>
                </motion.div>

                {/* API Option */}
                <motion.div
                    whileHover={{ scale: 1.02 }}
                    whileTap={{ scale: 0.98 }}
                    transition={{ type: "spring", stiffness: 400, damping: 17 }}
                >
                    <Card
                        className="cursor-pointer opacity-75 hover:opacity-90 transition-opacity relative overflow-hidden"
                        onClick={handleAPIClick}
                    >
                        <CardHeader>
                            <CardTitle className="flex items-center gap-2">
                                Generate via API
                                <AlertCircle className="h-4 w-4 text-yellow-500" />
                            </CardTitle>
                            <CardDescription>Use our API to generate barcodes programmatically.</CardDescription>
                        </CardHeader>
                        <div className="absolute inset-0 bg-background/10 backdrop-blur-[1px]" />
                    </Card>
                </motion.div>
            </div>

            <AnimatePresence>
                {showWebOptions && (
                    <motion.div
                        variants={optionsVariants}
                        initial="hidden"
                        animate="visible"
                        exit="hidden"
                        className="mt-6"
                    >
                        <Card>
                            <CardContent className="pt-6">
                                <BulkWebOptions />
                            </CardContent>
                        </Card>
                    </motion.div>
                )}
            </AnimatePresence>
        </motion.div>
    );
}