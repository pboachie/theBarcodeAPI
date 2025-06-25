import React from 'react';
import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';
import '@testing-library/jest-dom';
import BulkWebOptions from '../BulkWebOptions'; // Adjust path as needed
import { useToast } from '@/components/ui/use-toast';

// Mock useToast
jest.mock('@/components/ui/use-toast', () => ({
  useToast: () => ({
    toast: jest.fn(),
  }),
}));

// Helper to create File objects
const createFile = (name: string, type: string, size: number = 1024): File => {
  return new File(['dummy content'.repeat(size / 10)], name, { type });
};

describe('BulkWebOptions Component', () => {
  let mockToast: jest.Mock;

  beforeEach(() => {
    // Reset mocks before each test
    mockToast = jest.fn();
    (useToast as jest.Mock).mockReturnValue({ toast: mockToast });

    // Mock global fetch
    global.fetch = jest.fn();
  });

  afterEach(() => {
    jest.clearAllMocks();
  });

  test('renders correctly with initial elements', () => {
    render(<BulkWebOptions />);

    // Check for the main drop zone / file input area
    expect(screen.getByText(/upload files or drag & drop/i)).toBeInTheDocument();
    expect(screen.getByText(/click to browse or drag & drop files/i)).toBeInTheDocument();

    // Check for the submit button
    expect(screen.getByRole('button', { name: /generate barcodes for files/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /generate barcodes for files/i })).toBeDisabled();
  });

  describe('File Input and Validation', () => {
    test('allows selecting valid files via click and updates list', async () => {
      render(<BulkWebOptions />);
      const fileInput = screen.getByLabelText(/upload files or drag & drop/i).querySelector('input[type="file"]') as HTMLInputElement;

      const testFile1 = createFile('test1.txt', 'text/plain');
      const testFile2 = createFile('test2.csv', 'text/csv');

      await act(async () => {
        fireEvent.change(fileInput, { target: { files: [testFile1, testFile2] } });
      });

      expect(screen.getByText(testFile1.name)).toBeInTheDocument();
      expect(screen.getByText(testFile2.name)).toBeInTheDocument();
      expect(screen.getByText(/selected files \(2\/5\):/i)).toBeInTheDocument();
      expect(mockToast).toHaveBeenCalledWith(expect.objectContaining({ title: "Files ready" }));
      expect(screen.getByRole('button', { name: /generate barcodes for 2 file\(s\)/i })).not.toBeDisabled();
    });

    test('prevents adding more than MAX_FILES (5)', async () => {
        render(<BulkWebOptions />);
        const fileInput = screen.getByLabelText(/upload files or drag & drop/i).querySelector('input[type="file"]') as HTMLInputElement;

        const filesToSelect = [
          createFile('1.txt', 'text/plain'),
          createFile('2.txt', 'text/plain'),
          createFile('3.txt', 'text/plain'),
          createFile('4.txt', 'text/plain'),
          createFile('5.txt', 'text/plain'),
          createFile('6.txt', 'text/plain'), // This one should be rejected
        ];

        await act(async () => {
          fireEvent.change(fileInput, { target: { files: filesToSelect } });
        });

        expect(screen.getByText('1.txt')).toBeInTheDocument();
        expect(screen.getByText('5.txt')).toBeInTheDocument();
        expect(screen.queryByText('6.txt')).not.toBeInTheDocument();
        expect(screen.getByText(/selected files \(5\/5\):/i)).toBeInTheDocument();
        expect(mockToast).toHaveBeenCalledWith(expect.objectContaining({ title: 'File limit reached' }));
      });

      test('rejects invalid file types and shows toast', async () => {
        render(<BulkWebOptions />);
        const fileInput = screen.getByLabelText(/upload files or drag & drop/i).querySelector('input[type="file"]') as HTMLInputElement;

        const validFile = createFile('good.txt', 'text/plain');
        const invalidFile = createFile('bad.exe', 'application/octet-stream');

        await act(async () => {
          fireEvent.change(fileInput, { target: { files: [validFile, invalidFile] } });
        });

        expect(screen.getByText(validFile.name)).toBeInTheDocument();
        expect(screen.queryByText(invalidFile.name)).not.toBeInTheDocument();
        expect(mockToast).toHaveBeenCalledWith(expect.objectContaining({
          title: 'Invalid file type',
          description: `${invalidFile.name} unsupported. Allowed: TXT, CSV, XLS, XLSX.`,
          variant: 'destructive',
        }));
      });

      test('allows removing a selected file', async () => {
        render(<BulkWebOptions />);
        const fileInput = screen.getByLabelText(/upload files or drag & drop/i).querySelector('input[type="file"]') as HTMLInputElement;
        const testFile = createFile('to_remove.txt', 'text/plain');

        await act(async () => {
          fireEvent.change(fileInput, { target: { files: [testFile] } });
        });

        expect(screen.getByText(testFile.name)).toBeInTheDocument();

        const removeButton = screen.getByRole('button', { name: `Remove ${testFile.name}` });
        await act(async () => {
            fireEvent.click(removeButton);
        });

        expect(screen.queryByText(testFile.name)).not.toBeInTheDocument();
        expect(screen.getByText(/selected files \(0\/5\):/i)).toBeInTheDocument(); // Or just "Selected Files" if count is hidden at 0
        expect(mockToast).toHaveBeenCalledWith(expect.objectContaining({ title: 'File removed' }));
        expect(screen.getByRole('button', { name: /generate barcodes for files/i })).toBeDisabled();
      });
  });

  describe('Drag and Drop File Input', () => {
    test('allows adding valid files via drag and drop', async () => {
      render(<BulkWebOptions />);
      const dropZone = screen.getByText(/click to browse or drag & drop files/i).closest('div') as HTMLElement;

      const testFile1 = createFile('dragged1.txt', 'text/plain');
      const testFile2 = createFile('dragged2.csv', 'text/csv');
      const dataTransfer = new DataTransfer();
      dataTransfer.items.add(testFile1);
      dataTransfer.items.add(testFile2);

      await act(async () => {
        fireEvent.dragOver(dropZone, { dataTransfer }); // Simulate drag over
      });
      // Could check for isDragging class if UI changes significantly

      await act(async () => {
        fireEvent.drop(dropZone, { dataTransfer });
      });

      expect(screen.getByText(testFile1.name)).toBeInTheDocument();
      expect(screen.getByText(testFile2.name)).toBeInTheDocument();
      expect(screen.getByText(/selected files \(2\/5\):/i)).toBeInTheDocument();
      expect(mockToast).toHaveBeenCalledWith(expect.objectContaining({ title: "Files ready" }));
    });

    test('prevents adding more than MAX_FILES via drag and drop', async () => {
        render(<BulkWebOptions />);
        const dropZone = screen.getByText(/click to browse or drag & drop files/i).closest('div') as HTMLElement;

        const filesToDrop = [
            createFile('d1.txt', 'text/plain'), createFile('d2.txt', 'text/plain'),
            createFile('d3.txt', 'text/plain'), createFile('d4.txt', 'text/plain'),
            createFile('d5.txt', 'text/plain'), createFile('d6.txt', 'text/plain'), // excess
        ];
        const dataTransfer = new DataTransfer();
        filesToDrop.forEach(f => dataTransfer.items.add(f));

        await act(async () => {
          fireEvent.drop(dropZone, { dataTransfer });
        });

        expect(screen.getByText('d1.txt')).toBeInTheDocument();
        expect(screen.getByText('d5.txt')).toBeInTheDocument();
        expect(screen.queryByText('d6.txt')).not.toBeInTheDocument();
        expect(mockToast).toHaveBeenCalledWith(expect.objectContaining({ title: 'File limit reached' }));
      });

      test('rejects invalid file types via drag and drop', async () => {
        render(<BulkWebOptions />);
        const dropZone = screen.getByText(/click to browse or drag & drop files/i).closest('div') as HTMLElement;

        const validFile = createFile('d_good.txt', 'text/plain');
        const invalidFile = createFile('d_bad.exe', 'application/octet-stream');
        const dataTransfer = new DataTransfer();
        dataTransfer.items.add(validFile);
        dataTransfer.items.add(invalidFile);

        await act(async () => {
          fireEvent.drop(dropZone, { dataTransfer });
        });

        expect(screen.getByText(validFile.name)).toBeInTheDocument();
        expect(screen.queryByText(invalidFile.name)).not.toBeInTheDocument();
        expect(mockToast).toHaveBeenCalledWith(expect.objectContaining({
          title: 'Invalid file type',
          description: `${invalidFile.name} unsupported. Allowed: TXT, CSV, XLS, XLSX.`,
        }));
      });
  });

  describe('Form Submission and API Interaction', () => {
    beforeEach(() => {
        // Ensure fetch is reset before each test in this block
        (global.fetch as jest.Mock).mockClear();
      });

    test('successful submission starts job and polling, then shows COMPLETED', async () => {
      // Mock initial upload response
      (global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          job_id: 'job123',
          estimated_completion_time: '10 seconds',
          files_processed: [{ filename: 'test.txt', content_type: 'text/plain', item_count: 1, status: 'Uploaded' }],
        }),
      });
      // Mock first status poll response (PENDING)
      (global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          job_id: 'job123', status: 'PENDING', progress_percentage: 0,
          files: [{ filename: 'test.txt', content_type: 'text/plain', item_count: 1, status: 'Processing' }],
        }),
      });
      // Mock second status poll response (COMPLETED)
      (global.fetch as jest.Mock).mockResolvedValueOnce({
        ok: true,
        json: async () => ({
          job_id: 'job123', status: 'COMPLETED', progress_percentage: 100,
          files: [{ filename: 'test.txt', content_type: 'text/plain', item_count: 1, status: 'Completed' }],
          results: [{ original_data: 'data1', output_filename: 'data1.png', status: 'Generated', barcode_image_url: 'data:image/png;base64,test' }],
        }),
      });

      jest.useFakeTimers(); // Use Jest's fake timers for setTimeout

      render(<BulkWebOptions />);
      const fileInput = screen.getByLabelText(/upload files or drag & drop/i).querySelector('input[type="file"]') as HTMLInputElement;
      const testFile = createFile('test.txt', 'text/plain');

      await act(async () => {
        fireEvent.change(fileInput, { target: { files: [testFile] } });
      });

      const submitButton = screen.getByRole('button', { name: /generate barcodes for 1 file\(s\)/i });
      await act(async () => {
        fireEvent.click(submitButton);
      });

      // Verify initial upload call
      expect(global.fetch).toHaveBeenCalledWith('/api/bulk/generate_upload', expect.any(Object));
      expect(mockToast).toHaveBeenCalledWith(expect.objectContaining({ title: 'Bulk job started!' }));

      // UI should update to show processing state
      await waitFor(() => expect(screen.getByText(/job status/i)).toBeInTheDocument());
      expect(screen.getByText(/job id: job123/i)).toBeInTheDocument();
      expect(screen.getByText(/estimated completion: 10 seconds/i)).toBeInTheDocument();

      // Fast-forward timers for the first poll
      await act(async () => {
        jest.advanceTimersByTime(3000);
      });
      await waitFor(() => expect(global.fetch).toHaveBeenCalledWith('/api/bulk/bulk_job_status/job123', undefined));
      await waitFor(() => expect(screen.getByText(/status: pending/i)).toBeInTheDocument()); // Or PROCESSING based on mock

      // Fast-forward timers for the second poll
      await act(async () => {
        jest.advanceTimersByTime(3000);
      });
      await waitFor(() => expect(global.fetch).toHaveBeenCalledWith('/api/bulk/bulk_job_status/job123', undefined)); // Called again

      // Verify final state
      await waitFor(() => expect(screen.getByText(/status: completed/i)).toBeInTheDocument());
      expect(screen.getByText(/100% complete/i)).toBeInTheDocument();
      expect(screen.getByAltText(/barcode for data1/i)).toBeInTheDocument(); // Check for img tag
      expect(screen.getByRole('button', { name: /start new bulk job/i})).toBeInTheDocument(); // New job button

      jest.useRealTimers(); // Restore real timers
    });

    test('handles submission error from upload endpoint', async () => {
        (global.fetch as jest.Mock).mockResolvedValueOnce({
          ok: false,
          json: async () => ({ detail: 'Test submission error' }),
        });

        render(<BulkWebOptions />);
        const fileInput = screen.getByLabelText(/upload files or drag & drop/i).querySelector('input[type="file"]') as HTMLInputElement;
        const testFile = createFile('error_test.txt', 'text/plain');
        await act(async () => {
          fireEvent.change(fileInput, { target: { files: [testFile] } });
        });

        const submitButton = screen.getByRole('button', { name: /generate barcodes for 1 file\(s\)/i });
        await act(async () => {
          fireEvent.click(submitButton);
        });

        await waitFor(() => expect(screen.getByText(/error: test submission error/i)).toBeInTheDocument());
        expect(mockToast).toHaveBeenCalledWith(expect.objectContaining({ title: 'Submission Error', variant: 'destructive' }));
        expect(screen.queryByText(/job status/i)).not.toBeInTheDocument(); // No job status section
      });

      test('handles polling error and stops polling', async () => {
        (global.fetch as jest.Mock).mockResolvedValueOnce({ // Initial successful upload
          ok: true,
          json: async () => ({ job_id: 'job456', estimated_completion_time: '5s', files_processed: [] }),
        });
        (global.fetch as jest.Mock).mockResolvedValueOnce({ // First poll fails
          ok: false,
          json: async () => ({ detail: 'Test polling error' }),
        });

        jest.useFakeTimers();
        render(<BulkWebOptions />);
        const fileInput = screen.getByLabelText(/upload files or drag & drop/i).querySelector('input[type="file"]') as HTMLInputElement;
        const testFile = createFile('poll_error.txt', 'text/plain');
        await act(async () => {
          fireEvent.change(fileInput, { target: { files: [testFile] } });
        });
        const submitButton = screen.getByRole('button', { name: /generate barcodes for 1 file\(s\)/i });
        await act(async () => {
          fireEvent.click(submitButton);
        });

        await waitFor(() => expect(global.fetch).toHaveBeenCalledWith('/api/bulk/generate_upload', expect.any(Object)));

        await act(async () => { jest.advanceTimersByTime(3000); }); // Trigger first poll

        await waitFor(() => expect(screen.getByText(/error during processing: test polling error/i)).toBeInTheDocument());
        expect(mockToast).toHaveBeenCalledWith(expect.objectContaining({ title: 'Status Error', variant: 'destructive' }));

        // Ensure fetch is not called again for polling
        (global.fetch as jest.Mock).mockClear(); // Clear previous fetch calls
        await act(async () => { jest.advanceTimersByTime(3500); }); // Advance time past another polling interval
        expect(global.fetch).not.toHaveBeenCalled(); // Should not have polled again

        jest.useRealTimers();
      });
  });

  describe('Display Logic', () => {
    test('updates progress bar and displays per-item errors correctly', async () => {
        // Mock initial upload response
        (global.fetch as jest.Mock).mockResolvedValueOnce({
          ok: true,
          json: async () => ({
            job_id: 'job789',
            estimated_completion_time: '12 seconds',
            files_processed: [{ filename: 'mixed_results.txt', content_type: 'text/plain', item_count: 2, status: 'Uploaded' }],
          }),
        });
        // Mock status poll response (PARTIAL_SUCCESS)
        (global.fetch as jest.Mock).mockResolvedValueOnce({
          ok: true,
          json: async () => ({
            job_id: 'job789', status: 'PARTIAL_SUCCESS', progress_percentage: 100, // Assume 100% as all attempted
            files: [{ filename: 'mixed_results.txt', content_type: 'text/plain', item_count: 2, status: 'Completed' }],
            results: [
              { original_data: 'good_data', output_filename: 'good_data.png', status: 'Generated', barcode_image_url: 'data:image/png;base64,good' },
              { original_data: 'bad_data', output_filename: 'bad_data.png', status: 'Failed', error_message: 'Invalid characters' },
            ],
          }),
        });

        jest.useFakeTimers();
        render(<BulkWebOptions />);
        const fileInput = screen.getByLabelText(/upload files or drag & drop/i).querySelector('input[type="file"]') as HTMLInputElement;
        const testFile = createFile('mixed_results.txt', 'text/plain');

        await act(async () => { fireEvent.change(fileInput, { target: { files: [testFile] } }); });
        const submitButton = screen.getByRole('button', { name: /generate barcodes for 1 file\(s\)/i });
        await act(async () => { fireEvent.click(submitButton); });

        // Wait for initial job setup
        await waitFor(() => expect(screen.getByText(/job id: job789/i)).toBeInTheDocument());

        // Trigger poll
        await act(async () => { jest.advanceTimersByTime(3000); });

        // Verify final state with progress and results
        await waitFor(() => expect(screen.getByText(/status: partial success/i)).toBeInTheDocument());

        // Check progress bar (aria-valuenow is a good way to check Radix Progress)
        const progressBar = screen.getByRole('progressbar');
        expect(progressBar).toHaveAttribute('aria-valuenow', '100');
        // Or check the visual style if possible, e.g., `expect(progressBar.querySelector('div')).toHaveStyle('width: 100%');`

        // Check for successful item display
        expect(screen.getByAltText(/barcode for good_data/i)).toBeInTheDocument();

        // Check for failed item display and its error message
        expect(screen.getByText('bad_data.png')).toBeInTheDocument(); // Or original_data if filename not available
        expect(screen.getByText(/error: invalid characters/i)).toBeInTheDocument();

        jest.useRealTimers();
      });
  });
});
