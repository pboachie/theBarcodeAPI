//src/components/ui/alert.js

import React from 'react';

export const Alert = React.forwardRef(({ className, ...props }, ref) => {
  return (
    <div ref={ref} role="alert" className={`rounded-lg border p-4 ${className}`} {...props} />
  );
});
Alert.displayName = "Alert";

export const AlertTitle = React.forwardRef(({ className, ...props }, ref) => {
  return (
    <h5 ref={ref} className={`font-medium ${className}`} {...props} />
  );
});
AlertTitle.displayName = "AlertTitle";

export const AlertDescription = React.forwardRef(({ className, ...props }, ref) => {
  return (
    <div ref={ref} className={`mt-2 text-sm ${className}`} {...props} />
  );
});
AlertDescription.displayName = "AlertDescription";