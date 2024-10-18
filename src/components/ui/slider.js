//src/components/ui.slider.js

import React, { useState, useRef, useEffect, useCallback } from 'react';

export const Slider = ({ min, max, step, value, onValueChange, disabled, className }) => {
  const [isDragging, setIsDragging] = useState(false);
  const sliderRef = useRef(null);
  const thumbRef = useRef(null);

  const getPercentage = (value) => ((value - min) / (max - min)) * 100;

  const updateValue = useCallback(
    (event) => {
      const sliderRect = sliderRef.current.getBoundingClientRect();
      const percentage = (event.clientX - sliderRect.left) / sliderRect.width;
      const newValue = Math.round((percentage * (max - min) + min) / step) * step;
      onValueChange(Math.max(min, Math.min(max, newValue)));
    },
    [min, max, step, onValueChange]
  );

  const handleMouseDown = (event) => {
    if (!disabled) {
      setIsDragging(true);
      updateValue(event);
    }
  };

  const handleMouseUp = useCallback(() => {
    setIsDragging(false);
  }, []);

  const handleMouseMove = useCallback(
    (event) => {
      if (isDragging) {
        updateValue(event);
      }
    },
    [isDragging, updateValue]
  );

  useEffect(() => {
    document.addEventListener('mousemove', handleMouseMove);
    document.addEventListener('mouseup', handleMouseUp);
    return () => {
      document.removeEventListener('mousemove', handleMouseMove);
      document.removeEventListener('mouseup', handleMouseUp);
    };
  }, [handleMouseMove, handleMouseUp]);

  return (
    <div ref={sliderRef} className={`relative ${className}`} onMouseDown={handleMouseDown}>
      <div className="absolute top-1/2 left-0 right-0 h-1 bg-gray-300 rounded-full transform -translate-y-1/2">
        <div
          className="absolute top-0 left-0 h-full bg-blue-500 rounded-full"
          style={{ width: `${getPercentage(value)}%` }}
        ></div>
      </div>
      <div
        ref={thumbRef}
        className="absolute top-1/2 w-4 h-4 bg-blue-500 rounded-full shadow transform -translate-x-1/2 -translate-y-1/2 cursor-pointer"
        style={{ left: `${getPercentage(value)}%` }}
      ></div>
    </div>
  );
};
