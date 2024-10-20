//src/components/ui/card.js

import React from 'react';

export const Card = React.forwardRef(({ className, ...props }, ref) => {
  return (
    <div ref={ref} className={`rounded-lg border bg-card text-card-foreground shadow-sm ${className}`} {...props} />
  );
});
Card.displayName = "Card";

export const CardHeader = React.forwardRef(({ className, ...props }, ref) => {
  return (
    <div ref={ref} className={`flex flex-col space-y-1.5 p-6 ${className}`} {...props} />
  );
});
CardHeader.displayName = "CardHeader";

export const CardContent = React.forwardRef(({ className, ...props }, ref) => {
  return (
    <div ref={ref} className={`p-6 pt-0 ${className}`} {...props} />
  );
});
CardContent.displayName = "CardContent";