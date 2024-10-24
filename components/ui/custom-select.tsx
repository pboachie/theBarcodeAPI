import React, { useState, useRef, useEffect } from 'react';
import { ChevronDown } from 'lucide-react';

interface CustomSelectProps {
  options: string[];
  value: string;
  onChange: (value: string) => void;
  placeholder: string;
}

import styles from './custom-select.module.css';

export const CustomSelect: React.FC<CustomSelectProps> = ({ options, value, onChange, placeholder }) => {
  const [isOpen, setIsOpen] = useState(false);
  const [isMounted, setIsMounted] = useState(false);
  const selectRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    setIsMounted(true);
    const handleClickOutside = (event: MouseEvent) => {
      if (selectRef.current && !selectRef.current.contains(event.target as Node)) {
        setIsOpen(false);
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, []);

  if (!isMounted) {
    return (
      <div className={styles.customSelect}>
        <div className={styles.customSelectTrigger}>
          <span className={styles.customSelectText}>{value || placeholder}</span>
          <ChevronDown className={styles.customSelectArrow} />
        </div>
      </div>
    );
  }

  return (
    <div className={styles.customSelect} ref={selectRef}>
      <div
        className={styles.customSelectTrigger}
        onClick={() => setIsOpen(!isOpen)}
      >
        <span className={styles.customSelectText}>{value || placeholder}</span>
        <ChevronDown className={`${styles.customSelectArrow} ${isOpen ? styles.open : ''}`} />
      </div>
      {isOpen && (
        <div className={styles.customOptions}>
          {options.map((option) => (
            <div
              key={option}
              className={`${styles.customOption} ${value === option ? styles.selected : ''}`}
              onClick={() => {
                onChange(option);
                setIsOpen(false);
              }}
            >
              {option}
            </div>
          ))}
        </div>
      )}
    </div>
  );
};
export default CustomSelect;