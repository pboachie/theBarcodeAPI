//src/components/ui/switch.js

import React from 'react';

export const Switch = React.forwardRef(({ className, ...props }, ref) => {
  return (
    <input
      type="checkbox"
      role="switch"
      className={`h-6 w-11 rounded-full bg-gray-200 peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-blue-600 ${className}`}
      ref={ref}
      {...props}
    />
  );
});
Switch.displayName = "Switch";