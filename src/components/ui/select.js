// src/components/ui/select.js

import React, { useState, useRef, useEffect } from 'react';

export const Select = ({ value, onValueChange, children, disabled, placeholder }) => {
  const [isOpen, setIsOpen] = useState(false);
  const selectRef = useRef(null);

  useEffect(() => {
    const handleClickOutside = (event) => {
      if (selectRef.current && !selectRef.current.contains(event.target)) {
        setIsOpen(false);
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, []);

  const handleToggle = () => {
    if (!disabled) {
      setIsOpen(!isOpen);
    }
  };

  const handleSelect = (selectedValue) => {
    onValueChange(selectedValue);
    setIsOpen(false);
  };

  return (
    <div className="relative" ref={selectRef}>
      <SelectTrigger
        value={value}
        onClick={handleToggle}
        disabled={disabled}
        placeholder={placeholder}
      />
      {isOpen && (
        <SelectContent>
          {React.Children.map(children, (child) =>
            React.cloneElement(child, { onSelect: handleSelect })
          )}
        </SelectContent>
      )}
    </div>
  );
};

export const SelectTrigger = ({ value, onClick, disabled, placeholder }) => (
  <button
    className={`w-full p-2 text-left bg-white border rounded shadow ${
      disabled ? 'opacity-50 cursor-not-allowed' : 'hover:border-gray-400'
    }`}
    onClick={onClick}
    disabled={disabled}
  >
    {value || placeholder || 'Select an option'}
    <span className="float-right">▼</span>
  </button>
);

export const SelectContent = ({ children }) => (
  <div className="absolute z-10 w-full mt-1 bg-white border rounded shadow-lg">{children}</div>
);

export const SelectItem = ({ children, value, onSelect }) => (
  <div className="p-2 cursor-pointer hover:bg-gray-100" onClick={() => onSelect(value)}>
    {children}
  </div>
);

export const SelectValue = ({ children }) => children;
