//src/components/ui/card.js

import React from 'react';

export const Card = ({ children, className, ...props }) => (
  <div className={`bg-white shadow-lg rounded-lg ${className}`} {...props}>
    {children}
  </div>
);

export const CardHeader = ({ children, className, ...props }) => (
  <div className={`px-4 py-5 border-b border-gray-200 ${className}`} {...props}>
    {children}
  </div>
);

export const CardContent = ({ children, className, ...props }) => (
  <div className={`p-4 ${className}`} {...props}>
    {children}
  </div>
);
