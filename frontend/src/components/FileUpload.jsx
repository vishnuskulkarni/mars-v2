import { useState, useRef } from 'react';
import { Upload, X, FileText, Database } from 'lucide-react';

export default function FileUpload({ type, files, onFilesChange }) {
  const [isDragging, setIsDragging] = useState(false);
  const inputRef = useRef(null);

  const isLiterature = type === 'literature';
  const accept = isLiterature ? '.pdf' : '.csv,.xlsx,.xls';
  const Icon = isLiterature ? FileText : Database;
  const label = isLiterature ? 'Literature (PDFs)' : 'Data (CSV/Excel)';

  const handleDrag = (e) => {
    e.preventDefault();
    e.stopPropagation();
  };

  const handleDragIn = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(true);
  };

  const handleDragOut = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
  };

  const handleDrop = (e) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
    const droppedFiles = Array.from(e.dataTransfer.files);
    onFilesChange([...files, ...droppedFiles]);
  };

  const handleSelect = (e) => {
    const selected = Array.from(e.target.files);
    onFilesChange([...files, ...selected]);
  };

  const removeFile = (index) => {
    onFilesChange(files.filter((_, i) => i !== index));
  };

  const formatSize = (bytes) => {
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
    return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
  };

  return (
    <div>
      <label className="flex items-center gap-2 text-sm font-medium text-text-secondary mb-2">
        <Icon size={16} />
        {label}
      </label>

      <div
        onDragEnter={handleDragIn}
        onDragLeave={handleDragOut}
        onDragOver={handleDrag}
        onDrop={handleDrop}
        onClick={() => inputRef.current?.click()}
        className={`border-2 border-dashed rounded-lg p-6 text-center cursor-pointer transition-colors ${
          isDragging
            ? 'border-accent bg-accent/5'
            : 'border-border hover:border-text-secondary'
        }`}
      >
        <Upload size={20} className="mx-auto mb-2 text-text-secondary" />
        <p className="text-sm text-text-secondary">
          Drop files here or <span className="text-accent">browse</span>
        </p>
        <p className="text-xs text-text-secondary mt-1">
          {isLiterature ? 'PDF files' : 'CSV, XLSX, XLS files'} — max 50MB each
        </p>
        <input
          ref={inputRef}
          type="file"
          accept={accept}
          multiple
          onChange={handleSelect}
          className="hidden"
        />
      </div>

      {files.length > 0 && (
        <div className="mt-2 space-y-1">
          {files.map((f, i) => (
            <div key={i} className="flex items-center justify-between px-3 py-2 bg-surface rounded-lg">
              <div className="flex items-center gap-2 min-w-0">
                <Icon size={14} className="text-text-secondary shrink-0" />
                <span className="text-sm text-text-primary truncate">{f.name}</span>
                <span className="text-xs text-text-secondary shrink-0">{formatSize(f.size)}</span>
              </div>
              <button
                onClick={(e) => { e.stopPropagation(); removeFile(i); }}
                className="p-1 rounded hover:bg-bg text-text-secondary hover:text-error"
              >
                <X size={14} />
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
