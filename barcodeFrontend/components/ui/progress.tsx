import React from 'react';

interface ProgressProps extends React.HTMLAttributes<HTMLDivElement> {
  value?: number;
}

const Progress = React.forwardRef<HTMLDivElement, ProgressProps>(
  ({ className, value, ...props }, ref) => {
    return (
      <div ref={ref} className={`w-full h-2 bg-muted rounded overflow-hidden ${className || ''}`} {...props}>
        <div
          className="h-full bg-primary transition-all duration-300 ease-in-out"
          style={{ width: `${value || 0}%` }}
          data-testid="progress-bar-inner"
        />
      </div>
    );
  }
);
Progress.displayName = "Progress";

export { Progress };
