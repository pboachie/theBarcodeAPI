// FormatSelector.tsx

import React from 'react';
import { useMediaQuery } from 'react-responsive';
import { Button } from "@/components/ui/button";
import { CustomSelect } from "@/components/ui/custom-select";

interface FormatSelectorProps {
  title: string;
  options: readonly string[];
  value: string;
  onChange: (value: string) => void;
  disabled: boolean;
}

export const FormatSelector: React.FC<FormatSelectorProps> = ({
  title,
  options,
  value,
  onChange,
  disabled
}) => {
  const isMobile = useMediaQuery({ maxWidth: 767 });

  if (isMobile) {
    return (
      <div>
        <label className="block text-sm font-medium mb-1">{title}</label>
        <CustomSelect
          options={options.map(opt => opt.toUpperCase())}
          value={value.toUpperCase()}
          onChange={(val) => onChange(val.toLowerCase())}
          placeholder={`Select ${title.toLowerCase()}`}
        />
      </div>
    );
  }

  return (
    <div>
      <label className="block text-sm font-medium mb-1">{title}</label>
      <div className="flex flex-wrap gap-2">
        {options.map(opt => (
          <Button
            key={opt}
            className="barcode-type-button"
            variant={value === opt ? "outline" : "default"}
            size={isMobile ? "sm" : "lg"}
            onClick={() => onChange(opt)}
            disabled={disabled}
            data-state={value === opt ? "active" : "inactive"}
          >
            {opt.toUpperCase()}
          </Button>
        ))}
      </div>
    </div>
  );
};
