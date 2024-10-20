//src/components/ui.slider.js

import React from 'react';

export const Slider = React.forwardRef(({ className, ...props }, ref) => {
  return (
    <input
      type="range"
      className={`w-full ${className}`}
      ref={ref}
      {...props}
    />
  );
});
Slider.displayName = "Slider";