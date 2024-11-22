// SupportForm.tsx
'use client';

import { useState } from 'react';
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { motion, AnimatePresence } from 'framer-motion';

export default function SupportForm() {
  const [submitted, setSubmitted] = useState(false);

  const formVariants = {
    hidden: { opacity: 0 },
    visible: {
      opacity: 1,
      transition: {
        staggerChildren: 0.1
      }
    }
  };

  const itemVariants = {
    hidden: { opacity: 0, y: 20 },
    visible: {
      opacity: 1,
      y: 0,
      transition: { duration: 0.3 }
    }
  };

  return (
    <AnimatePresence mode="wait">
      {!submitted ? (
        <motion.form
          onSubmit={(e) => {
            e.preventDefault();
            setSubmitted(true);
          }}
          className="space-y-4"
          variants={formVariants}
          initial="hidden"
          animate="visible"
          exit="hidden"
        >
          <motion.div variants={itemVariants} className="grid grid-cols-2 gap-4">
            <div>
              <Label htmlFor="name">Name</Label>
              <Input
                id="name"
                name="name"
                required
                placeholder="Your name"
                aria-label="Your name"
              />
            </div>
            <div>
              <Label htmlFor="email">Email</Label>
              <Input
                type="email"
                id="email"
                name="email"
                required
                placeholder="Your email"
                aria-label="Your email address"
              />
            </div>
          </motion.div>

          <motion.div variants={itemVariants}>
            <Label htmlFor="message">Message</Label>
            <Textarea
              id="message"
              name="message"
              required
              placeholder="How can we help you with your barcode generation needs?"
              className="h-24 resize-none"
              aria-label="Your message"
            />
          </motion.div>

          <motion.div variants={itemVariants}>
            <Button
              type="submit"
              className="w-full"
              aria-label="Submit support request"
            >
              Send Message
            </Button>
          </motion.div>
        </motion.form>
      ) : (
        <motion.div
          initial={{ opacity: 0, scale: 0.9 }}
          animate={{ opacity: 1, scale: 1 }}
          exit={{ opacity: 0, scale: 0.9 }}
          className="text-center py-4"
        >
          <h3 className="font-semibold text-primary mb-2">Thank you for reaching out!</h3>
          <p className="text-sm text-muted-foreground">Unfortunately, this feature is currently under development and will be available soon. Thank you for your patience.</p>
        </motion.div>
      )}
    </AnimatePresence>
  );
}