import React from 'react';
import { render, screen } from '@testing-library/react';
import '@testing-library/jest-dom';
import { Progress } from './progress';

describe('Progress Component', () => {
  // Test for default rendering
  test('renders with default props', () => {
    render(<Progress value={50} />);
    const progressBar = screen.getByTestId('progress-bar-inner');
    expect(progressBar).toBeInTheDocument();
    expect(progressBar).toHaveStyle('width: 50%');
    expect(progressBar).toHaveClass('bg-primary');
  });

  // Test for value clamping (value > 100)
  test('clamps value to 100 if value > 100', () => {
    render(<Progress value={150} />);
    const progressBar = screen.getByTestId('progress-bar-inner');
    expect(progressBar).toHaveStyle('width: 100%');
  });

  // Test for value clamping (value < 0)
  test('clamps value to 0 if value < 0', () => {
    render(<Progress value={-50} />);
    const progressBar = screen.getByTestId('progress-bar-inner');
    expect(progressBar).toHaveStyle('width: 0%');
  });

  // Test for indeterminate prop
  test('renders in indeterminate state', () => {
    render(<Progress indeterminate />);
    const progressBar = screen.getByTestId('progress-bar-inner');
    expect(progressBar).toHaveClass('animate-pulse');
    expect(progressBar).toHaveStyle('width: 100%'); // Indeterminate should fill the bar
  });

  // Test for showPercentage prop
  test('displays percentage text when showPercentage is true', () => {
    render(<Progress value={75} showPercentage />);
    const percentageText = screen.getByText('75%');
    expect(percentageText).toBeInTheDocument();
    expect(percentageText).toHaveClass('text-white'); // Assuming white text for visibility
  });

  // Test that percentage text is NOT displayed when showPercentage is false or default
  test('does not display percentage text by default or when showPercentage is false', () => {
    render(<Progress value={75} />);
    const percentageText = screen.queryByText('75%');
    expect(percentageText).not.toBeInTheDocument();
  });

  // Test that percentage text is NOT displayed when indeterminate is true, even if showPercentage is true
  test('does not display percentage text when indeterminate, even if showPercentage is true', () => {
    render(<Progress value={75} indeterminate showPercentage />);
    const percentageText = screen.queryByText('75%');
    expect(percentageText).not.toBeInTheDocument();
  });

  // Test for status="complete"
  test('renders with complete status styling', () => {
    render(<Progress value={100} status="complete" />);
    const progressBar = screen.getByTestId('progress-bar-inner');
    expect(progressBar).toHaveClass('bg-green-500');
    expect(progressBar).not.toHaveClass('bg-primary'); // Should not have default primary color
    expect(progressBar).not.toHaveClass('bg-red-500'); // Should not have error color
  });

  // Test for status="error"
  test('renders with error status styling', () => {
    render(<Progress value={50} status="error" />);
    const progressBar = screen.getByTestId('progress-bar-inner');
    expect(progressBar).toHaveClass('bg-red-500');
    expect(progressBar).not.toHaveClass('bg-primary'); // Should not have default primary color
    expect(progressBar).not.toHaveClass('bg-green-500'); // Should not have complete color
  });

  // Test that status prop overrides indeterminate styling for color, but not animation
  test('status prop overrides color but not animation for indeterminate state', () => {
    render(<Progress indeterminate status="complete" />);
    const progressBar = screen.getByTestId('progress-bar-inner');
    expect(progressBar).toHaveClass('bg-green-500'); // Status color should take precedence
    expect(progressBar).toHaveClass('animate-pulse'); // Indeterminate animation should persist
    expect(progressBar).toHaveStyle('width: 100%');
  });

   // Test for className prop
  test('applies custom className to the root element', () => {
    const customClass = 'my-custom-progress';
    render(<Progress value={50} className={customClass} />);
    const progressContainer = screen.getByRole('progressbar'); // The outer div
    expect(progressContainer).toHaveClass(customClass);
  });
});
