import React from 'react';

interface ProgressProps extends React.HTMLAttributes<HTMLDivElement> {
  value?: number;
  indeterminate?: boolean;
  showPercentage?: boolean;
  status?: 'complete' | 'error';
}

const Progress = React.forwardRef<HTMLDivElement, ProgressProps>(
  ({ className, value, indeterminate, showPercentage, status, ...props }, ref) => {
    const percentage = Math.min(Math.max(value || 0, 0), 100); // Ensure percentage is between 0 and 100

    let baseProgressBarClassName = 'h-full transition-all duration-300 ease-in-out';
    let colorClassName = 'bg-primary'; // Default color

    if (status === 'complete') {
      colorClassName = 'bg-green-500'; // Green for complete
    } else if (status === 'error') {
      colorClassName = 'bg-red-500'; // Red for error
    }

    let progressBarClassName = `${baseProgressBarClassName} ${colorClassName}`;

    if (indeterminate) {
      // For indeterminate, status color applies, and it pulses.
      // Width is 100% for indeterminate, so no specific color logic needed other than what's set by status.
      progressBarClassName += ' animate-pulse';
    }


    return (
      <div
        ref={ref}
        role="progressbar" // Added ARIA role
        aria-valuenow={indeterminate ? undefined : percentage}
        aria-valuemin={indeterminate ? undefined : 0}
        aria-valuemax={indeterminate ? undefined : 100}
        className={`w-full h-4 bg-muted rounded overflow-hidden relative ${className || ''}`} // Increased height for percentage text
        {...props}
      >
        <div
          className={progressBarClassName}
          style={{ width: indeterminate ? '100%' : `${percentage}%` }}
          data-testid="progress-bar-inner"
        />
        {showPercentage && !indeterminate && (
          <div
            className="absolute inset-0 flex items-center justify-center text-xs text-white"
            data-testid="progress-percentage-text"
          >
            {`${percentage}%`}
          </div>
        )}
      </div>
    );
  }
);
Progress.displayName = 'Progress';

export { Progress };
