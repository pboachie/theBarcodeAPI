// src/components/ui/select.js

import React from 'react';

export const Select = React.forwardRef(({ children, ...props }, ref) => {
  return (
    <select ref={ref} {...props}>
      {children}
    </select>
  );
});
Select.displayName = "Select";

export const SelectContent = ({ children }) => <>{children}</>;
export const SelectItem = (props) => <option {...props} />;
export const SelectTrigger = ({ children }) => <>{children}</>;
export const SelectValue = () => null;