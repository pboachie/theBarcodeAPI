// SupportForm.tsx
'use client';

import { useState } from 'react';
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";

export default function SupportForm() {
  const [submitted, setSubmitted] = useState(false);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitted(true);
  };

  return !submitted ? (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div className="grid grid-cols-2 gap-4">
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
      </div>
      <div>
        <Label htmlFor="message">Message</Label>
        <Textarea
          id="message"
          name="message"
          required
          placeholder="How can we help you with your barcode generation needs?"
          className="h-24 resize-none"
          aria-label="Your message"
        />
      </div>
      <Button
        type="submit"
        className="w-full"
        aria-label="Submit support request"
      >
        Send Message
      </Button>
    </form>
  ) : (
    <div className="text-center py-4">
      <h3 className="font-semibold text-primary mb-2">Thank you for reaching out!</h3>
    <p className="text-sm text-muted-foreground">Unfortunately, this feature is currently under development and will be available soon. Thank you for your patience.</p>
    </div>
  );
}