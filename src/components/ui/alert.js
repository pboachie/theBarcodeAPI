import React from 'react';

export const Alert = ({ children, variant = 'default', className, ...props }) => {
  const variantClasses = {
    default: 'bg-blue-100 border-blue-500 text-blue-700',
    destructive: 'bg-red-100 border-red-500 text-red-700',
    success: 'bg-green-100 border-green-500 text-green-700',
    primary: 'bg-indigo-100 border-indigo-500 text-indigo-700',
    danger: 'bg-red-100 border-red-500 text-red-700',
  };

  return (
    <div
      className={`border-l-4 p-4 ${variantClasses[variant]} ${className}`}
      role="alert"
      {...props}
    >
      {children}
    </div>
  );
};

export const AlertTitle = ({ children, className, ...props }) => (
  <h3 className={`font-bold ${className}`} {...props}>
    {children}
  </h3>
);

export const AlertDescription = ({ children, className, ...props }) => (
  <p className={`mt-2 ${className}`} {...props}>
    {children}
  </p>
);
