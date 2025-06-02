'use client';

import React, { useState, useCallback, useEffect, useRef } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Upload, X, FileText, Loader2, AlertTriangle, Check, Download, /*Image as ImageIcon,*/ AlertCircle } from 'lucide-react'; // ImageIcon removed
import { useToast } from '@/components/ui/use-toast';
import { Progress } from '@/components/ui/progress'; // Progress is uncommented
import { motion, AnimatePresence } from 'framer-motion';

// Define types for job status and file metadata based on backend schemas
interface FileMetadata {
  filename: string;
  content_type: string;
  item_count: number;
  status: string;
  message?: string;
}

interface BarcodeResult {
  original_data: string;
  output_filename?: string;
  status: string;
  error_message?: string;
  barcode_image_url?: string;
}

interface JobStatusResponse {
  job_id: string;
  status: 'PENDING' | 'PROCESSING' | 'COMPLETED' | 'FAILED' | 'PARTIAL_SUCCESS';
  progress_percentage: number;
  results?: BarcodeResult[];
  error_message?: string;
  files: FileMetadata[];
}

const MAX_FILES = 5;
const ALLOWED_TYPES = [
  'text/plain',
  'text/csv',
  'application/vnd.ms-excel',
  'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
];

const itemVariants = {
  hidden: { opacity: 0, y: 10 },
  visible: (i: number) => ({
    opacity: 1,
    y: 0,
    transition: {
      delay: i * 0.05,
      duration: 0.3,
      ease: "easeOut"
    }
  }),
  exit: { opacity: 0, y: -10, transition: { duration: 0.2, ease: "easeIn" } }
};

export default function BulkWebOptions() {
  const [files, setFiles] = useState<File[]>([]);
  const [isDragging, setIsDragging] = useState(false);
  const { toast } = useToast();

  const [jobId, setJobId] = useState<string | null>(null);
  const [isProcessing, setIsProcessing] = useState<boolean>(false);
  const [processingError, setProcessingError] = useState<string | null>(null);
  const [jobStatus, setJobStatus] = useState<JobStatusResponse | null>(null);
  const [estimatedTime, setEstimatedTime] = useState<string | null>(null);
  const [fileProcessingInfo, setFileProcessingInfo] = useState<FileMetadata[]>([]);
  const pollingTimeoutRef = useRef<NodeJS.Timeout | null>(null);

  useEffect(() => {
    return () => {
      if (pollingTimeoutRef.current) {
        clearTimeout(pollingTimeoutRef.current);
      }
    };
  }, []);

  const processFiles = useCallback((incomingFiles: FileList | null) => {
    if (!incomingFiles) return;
    const newFilesArray: File[] = Array.from(incomingFiles);

    setFiles(prevFiles => {
      const currentFiles = [...prevFiles];
      const filesToAdd: File[] = []; // Changed to const
      let showMaxFilesToast = false;

      if (currentFiles.length >= MAX_FILES) {
        toast({ title: 'File limit reached', description: `You can upload a maximum of ${MAX_FILES} files.`, variant: 'default'});
        return currentFiles;
      }

      for (const file of newFilesArray) {
        if (currentFiles.length + filesToAdd.length >= MAX_FILES) {
          showMaxFilesToast = true;
          break;
        }
        if (!ALLOWED_TYPES.includes(file.type)) {
          toast({ title: 'Invalid file type', description: `${file.name} unsupported. Allowed: TXT, CSV, XLS, XLSX.`, variant: 'destructive'});
          continue;
        }
        if (currentFiles.some(ef => ef.name === file.name) || filesToAdd.some(nf => nf.name === file.name)) {
          toast({ title: 'Duplicate file', description: `${file.name} is already added or in selection.`, variant: 'default'});
          continue;
        }
        filesToAdd.push(file);
      }

      if (showMaxFilesToast) {
         toast({ title: 'File limit reached', description: `Some files were not added. Max ${MAX_FILES} files.`, variant: 'default'});
      }
      if (filesToAdd.length > 0) {
         toast({ title: 'Files ready', description: `${filesToAdd.length} file(s) added to the list.`});
      }
      return [...currentFiles, ...filesToAdd];
    });
  }, [toast]);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    processFiles(e.target.files);
    e.target.value = '';
  };

  const removeFile = (fileName: string) => {
    setFiles(prevFiles => prevFiles.filter(file => file.name !== fileName));
    toast({ title: "File removed", description: `${fileName} has been removed.` });
  };

  const handleDragOver = useCallback((e: React.DragEvent<HTMLDivElement>) => { e.preventDefault(); e.stopPropagation(); setIsDragging(true); }, []);
  const handleDragLeave = useCallback((e: React.DragEvent<HTMLDivElement>) => { e.preventDefault(); e.stopPropagation(); setIsDragging(false); }, []);
  const handleDrop = useCallback((e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault(); e.stopPropagation(); setIsDragging(false);
    processFiles(e.dataTransfer.files);
  }, [processFiles]);

  const pollJobStatus = useCallback(async (currentJobId: string) => {
    if (!currentJobId) return;
    try {
      const response = await fetch(`/api/bulk/bulk_job_status/${currentJobId}`);
      if (response.ok) {
        const statusData: JobStatusResponse = await response.json();
        setJobStatus(statusData);
        if(statusData.files) setFileProcessingInfo(statusData.files);

        if (statusData.status === 'PENDING' || statusData.status === 'PROCESSING') {
          pollingTimeoutRef.current = setTimeout(() => pollJobStatus(currentJobId), 3000);
        } else {
          setIsProcessing(false);
          toast({
            title: `Job ${statusData.status.replace('_', ' ')}`,
            description: `Job ${currentJobId} finished: ${statusData.status.replace('_', ' ')}. ${statusData.error_message || ''}`.trim(),
            variant: statusData.status === 'COMPLETED' || statusData.status === 'PARTIAL_SUCCESS' ? 'default' : 'destructive',
            duration: 7000,
          });
        }
      } else { /* ... error handling ... */ }
    } catch (_error) { /* ... error handling ... */ } // eslint-disable-line @typescript-eslint/no-unused-vars
  }, [toast, setJobStatus, setFileProcessingInfo, setIsProcessing]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setJobId(null); setJobStatus(null); setEstimatedTime(null); setFileProcessingInfo([]); setProcessingError(null);
    if (pollingTimeoutRef.current) clearTimeout(pollingTimeoutRef.current);
    if (files.length === 0) { toast({ title: 'No files selected', description: 'Please upload files.', variant: 'default'}); return; }

    setIsProcessing(true);
    const formData = new FormData();
    files.forEach(file => formData.append('files', file));

    try {
      const response = await fetch('/api/bulk/generate_upload', { method: 'POST', body: formData });
      if (response.ok) {
        const data = await response.json();
        setJobId(data.job_id); setEstimatedTime(data.estimated_completion_time); setFileProcessingInfo(data.files_processed); setFiles([]);
        toast({ title: 'Bulk job started!', description: `Job ID: ${data.job_id}. ${data.estimated_completion_time ? `Est. time: ${data.estimated_completion_time}` : ''}`});
        pollJobStatus(data.job_id);
      } else { /* ... error handling ... */ setIsProcessing(false); }
    } catch (_error) { /* ... error handling ... */ setIsProcessing(false); } // eslint-disable-line @typescript-eslint/no-unused-vars
  };

  const resetJobState = () => {
    setJobId(null); setJobStatus(null); setIsProcessing(false); setProcessingError(null);
    setEstimatedTime(null); setFileProcessingInfo([]); setFiles([]);
    if (pollingTimeoutRef.current) clearTimeout(pollingTimeoutRef.current);
  };

  const getFileStatusIcon = (status: string) => {
    if (status === 'Completed' || status === 'Generated' || status === 'Uploaded') return <Check className="h-4 w-4 text-green-500" />;
    if (status === 'Failed') return <AlertCircle className="h-4 w-4 text-red-500" />;
    return <Loader2 className="h-4 w-4 animate-spin text-blue-500" />;
  };

  return (
    <div className="mt-6 space-y-6">
      {/* File Upload Form (conditionally rendered) */}
      <AnimatePresence>
        {(!jobId && !isProcessing) && (
          <motion.form
            key="upload-form"
            initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0, y: -20 }}
            onSubmit={handleSubmit} className="space-y-6"
          >
            <div>
              <Label htmlFor="file-upload" className="mb-2 block font-semibold">Upload Files or Drag & Drop</Label>
              <div
                onDragOver={handleDragOver} onDragLeave={handleDragLeave} onDrop={handleDrop}
                className={`flex flex-col items-center justify-center p-8 border-2 border-dashed rounded-lg cursor-pointer ${isDragging ? 'border-primary bg-primary-foreground/20' : 'border-input hover:border-primary/70'} transition-all duration-200 ease-in-out`}
              >
                <Input type="file" id="file-upload" accept=".csv,.xlsx,.xls,.txt" onChange={handleFileChange} multiple className="hidden" disabled={isProcessing || !!jobId} />
                <label htmlFor="file-upload" className="cursor-pointer w-full h-full flex flex-col items-center justify-center text-center">
                  <Upload className="h-10 w-10 text-muted-foreground mb-3" />
                  <p className="text-md font-medium text-foreground">{isDragging ? 'Drop files here to upload' : 'Click to browse or drag & drop files'}</p>
                  <p className="text-sm text-muted-foreground mt-1">(Max {MAX_FILES} files. Supported: TXT, CSV, XLS, XLSX)</p>
                </label>
              </div>
              <AnimatePresence>
                {files.length > 0 && (
                  <motion.div layout className="mt-6 space-y-3">
                    <h3 className="text-md font-medium">Selected Files ({files.length}/{MAX_FILES}):</h3>
                    {files.map((file, idx) => (
                      <motion.div layout key={file.name} variants={itemVariants} initial="hidden" animate="visible" exit="exit" custom={idx} className="flex items-center justify-between p-3 border rounded-lg bg-card shadow-sm">
                        <div className="flex items-center space-x-3 overflow-hidden">
                            <FileText className="h-6 w-6 text-primary flex-shrink-0" />
                            <div className="flex flex-col overflow-hidden">
                               <span className="text-sm font-medium text-foreground truncate" title={file.name}>{file.name}</span>
                               <span className="text-xs text-muted-foreground">({(file.size / 1024).toFixed(2)} KB) - {file.type || 'unknown type'}</span>
                            </div>
                        </div>
                        <Button variant="ghost" size="sm" onClick={() => removeFile(file.name)} aria-label={`Remove ${file.name}`} className="flex-shrink-0 ml-2 text-muted-foreground hover:text-destructive" disabled={isProcessing || !!jobId}>
                          <X className="h-5 w-5" />
                        </Button>
                      </motion.div>
                    ))}
                  </motion.div>
                )}
              </AnimatePresence>

              <div className="mt-6 p-4 border rounded-lg bg-secondary/30 text-sm text-secondary-foreground">
                <h4 className="font-semibold mb-2 text-foreground">File Format Instructions:</h4>
                <ul className="list-disc pl-5 space-y-1 text-xs">
                  <li><strong>TXT Files:</strong> Each line should contain a single piece of data to be encoded in a barcode. Custom options per barcode are not supported via TXT.</li>
                  <li><strong>CSV/Excel Files:</strong>
                    <ul className="list-disc pl-5 mt-1 space-y-0.5">
                      <li>Ensure you have a column named <code>data</code> containing the content for each barcode.</li>
                      <li>Optionally, include a <code>filename</code> column to specify the output name for each barcode image (e.g., <code>mybarcode.png</code>). If not provided, a name will be generated.</li>
                      <li>You can also include columns for barcode customization:
                        <ul className="list-disc pl-5 mt-0.5 space-y-0.5">
                          <li><code>format</code>: e.g., CODE128, QR, EAN13. (Default: CODE128)</li>
                          <li><code>image_format</code>: e.g., PNG, JPEG, WEBP. (Default: PNG)</li>
                          <li><code>width</code>: (numeric) Desired image width in pixels.</li>
                          <li><code>height</code>: (numeric) Desired image height in pixels.</li>
                          <li><code>show_text</code>: (TRUE/FALSE) Whether to display text below the barcode.</li>
                          <li>Other options like <code>module_width</code>, <code>quiet_zone</code>, <code>font_size</code>, <code>text_distance</code>, <code>background</code>, <code>foreground</code>, <code>dpi</code>, <code>add_checksum</code>, <code>no_checksum</code>, <code>guardbar</code> are also supported. Refer to API documentation for full details.</li>
                        </ul>
                      </li>
                    </ul>
                  </li>
                  <li>Ensure column headers are exactly as specified (e.g., <code>data</code>, <code>format</code>).</li>
                </ul>
              </div>

            </div>
            <Button type="submit" disabled={files.length === 0 || isProcessing} className="w-full sm:w-auto text-base py-3 px-6">
              {isProcessing ? <Loader2 className="mr-2 h-5 w-5 animate-spin" /> : <Upload className="mr-2 h-5 w-5" />}
              {isProcessing ? 'Processing...' : `Generate Barcodes for ${files.length > 0 ? `${files.length} file(s)` : 'Files'}`}
            </Button>
          </motion.form>
        )}
      </AnimatePresence>

      {/* Processing Error (General) */}
      {processingError && !jobId && ( <div className="mt-4 p-4 bg-destructive/10 border border-destructive text-destructive-foreground rounded-lg shadow"> {/* ... */} </div>)}

      {/* Job Status Display Area */}
      {jobId && (
        <motion.div initial={{ opacity: 0 }} animate={{ opacity: 1 }} className="mt-6 p-6 border rounded-lg bg-card shadow-lg">
          {/* Item 1: Title and Button */}
          <div className="flex justify-between items-center mb-4">
            <h2 className="text-xl font-semibold text-foreground">Job Status</h2>
            { (jobStatus?.status === 'COMPLETED' || jobStatus?.status === 'PARTIAL_SUCCESS' || jobStatus?.status === 'FAILED') && (
                 <Button onClick={resetJobState} variant="outline" size="sm">Start New Bulk Job</Button>
            )}
          </div>
          {/* Item 2: Job ID */}
          <p className="text-sm text-muted-foreground"><strong>Job ID:</strong> <span className="font-mono">{jobId}</span></p>
          {/* Item 3: Estimated Time (conditional) */}
          {estimatedTime && (!jobStatus || jobStatus.status === 'PENDING' || jobStatus.status === 'PROCESSING') &&
            <p className="text-sm text-muted-foreground"><strong>Estimated Completion:</strong> {estimatedTime}</p>}

          <>
            {/* Item 4: Loader (conditional) - Original */}
            {isProcessing && (!jobStatus || jobStatus.status === 'PENDING' || jobStatus.status === 'PROCESSING') && ( <div className="flex items-center mt-4"><Loader2 className="mr-2 h-5 w-5 animate-spin" /> <p>Processing, please wait...</p></div> )}

            {jobStatus ? (
              <div className="mt-4">
                <div className="flex justify-between items-center mb-1">
                    <p className={`text-sm font-semibold ${
                        jobStatus.status === 'COMPLETED' ? 'text-green-600' :
                        jobStatus.status === 'PARTIAL_SUCCESS' ? 'text-yellow-600' :
                        jobStatus.status === 'FAILED' ? 'text-red-600' :
                        'text-blue-600'
                    }`}>Status: {jobStatus.status.replace('_', ' ')}</p>
                    <p className="text-sm text-muted-foreground">{jobStatus.progress_percentage}% complete</p>
                </div>
                <Progress
                  value={jobStatus.progress_percentage}
                  showPercentage
                  indeterminate={(jobStatus.status === 'PENDING' && jobStatus.progress_percentage === 0)}
                  status={
                    jobStatus.status === 'COMPLETED' ? 'complete' :
                    jobStatus.status === 'FAILED' ? 'error' :
                    undefined
                  }
                  className="w-full h-4 my-2" // Adjusted height for percentage text
                />
                {jobStatus.error_message && ( <p className="text-sm text-red-600 mt-2">Job Error: {jobStatus.error_message}</p> )}

                {/* File Processing Info (Animated) */}
                {fileProcessingInfo.length > 0 && (
                  <div className="mt-5">
                    <h3 className="text-lg font-medium mb-3 text-foreground">File Summary:</h3>
                    <motion.ul layout className="space-y-3">
                      {fileProcessingInfo.map((fp, index) => (
                        <motion.li layout key={`${fp.filename}-${index}`} variants={itemVariants} initial="hidden" animate="visible" exit="exit" custom={index}
                          className={`text-sm p-3 border rounded-md shadow-sm flex justify-between items-center transition-all duration-300 ease-in-out
                                     ${fp.status === 'Completed' || fp.status === 'Generated' || fp.status === 'Uploaded' ? 'bg-green-50 border-green-200' :
                                       fp.status === 'Failed' ? 'bg-red-50 border-red-200' : 'bg-blue-50 border-blue-200'}`}>
                          <div>
                            <p className="font-semibold text-foreground truncate pr-2" title={fp.filename}>{fp.filename}</p>
                            <p className="text-xs text-muted-foreground mt-1">{fp.content_type} - {fp.item_count} items</p>
                            {fp.message && <p className="text-xs mt-1 text-muted-foreground italic">{fp.message}</p>}
                          </div>
                          <div className="ml-2">{getFileStatusIcon(fp.status)}</div>
                        </motion.li>
                      ))}
                    </motion.ul>
                  </div>
                )}

                {/* Detailed Results Display - REINTRODUCING THIS BLOCK */}
                {(jobStatus.status === 'COMPLETED' || jobStatus.status === 'PARTIAL_SUCCESS') && jobStatus.results && jobStatus.results.length > 0 && (
                  <div className="mt-6">
                    <h3 className="text-lg font-medium mb-3 text-foreground">Generated Barcodes:</h3>
                    <div className="space-y-4">
                      {jobStatus.results.map((result, index) => (
                        <motion.div key={index} variants={itemVariants} initial="hidden" animate="visible" custom={index} // Changed custom prop
                          className={`p-4 border rounded-md shadow-sm ${result.status === 'Generated' ? 'bg-green-50/50' : 'bg-red-50/50'}`}
                        >
                          <p className="text-sm font-medium text-foreground">
                            {result.output_filename || result.original_data}
                          </p>
                          {result.status === 'Generated' && result.barcode_image_url ? (
                            result.barcode_image_url.startsWith('data:image/') ? (
                            // eslint-disable-next-line @next/next/no-img-element
                              <img src={result.barcode_image_url} alt={`Barcode for ${result.original_data}`} className="mt-2 max-w-xs mx-auto rounded border p-1" />
                            ) : (
                              <a href={result.barcode_image_url} target="_blank" rel="noopener noreferrer" className="text-xs text-blue-500 hover:underline block mt-1">
                                View Image (URL)
                              </a>
                            )
                          ) : result.status === 'Failed' && result.error_message ? (
                            <p className="text-xs text-red-600 mt-1">Error: {result.error_message}</p>
                          ) : null}
                        </motion.div>
                      ))}
                    </div>
                    <Button disabled className="mt-6 w-full sm:w-auto" variant="outline">
                      <Download className="mr-2 h-4 w-4" />
                      Download All as ZIP (Coming Soon)
                    </Button>
                  </div>
                )}
              </div>
            ) : null}

            {/* Original processingError && jobId conditional */}
            {processingError && jobId && ( <div className="mt-4 p-4 bg-red-500/10 border border-red-500 text-red-600 rounded-lg shadow"><AlertTriangle className="inline-block mr-2 h-5 w-5" />There was an error with this job. Details: {processingError}</div> )}
          </>
        </motion.div>
      )}
    </div>
  );
}
