// components/FileUpload.jsx
// Drag-and-drop + click-to-browse upload zone with image preview.
import { useCallback, useState, useRef } from 'react';
import { Upload, X, Film, Image as ImageIcon, FileCheck } from 'lucide-react';

const FORMAT_ICON = {
  image: ImageIcon,
  video: Film,
};

function ImagePreview({ file }) {
  const [src, setSrc] = useState(null);
  const [meta, setMeta] = useState(null);

  const loadPreview = useCallback((f) => {
    const reader = new FileReader();
    reader.onload = (e) => {
      setSrc(e.target.result);
      const img = new Image();
      img.onload = () => setMeta({ w: img.width, h: img.height });
      img.src = e.target.result;
    };
    reader.readAsDataURL(f);
  }, []);

  // Load preview whenever file changes
  useState(() => { if (file) loadPreview(file); }, [file]);

  if (!src) {
    loadPreview(file);
    return null;
  }

  return (
    <div className="mt-4 space-y-3">
      <div className="relative rounded-xl overflow-hidden border border-surface-border bg-surface-card">
        <img
          src={src}
          alt="Preview"
          className="w-full max-h-48 object-contain"
        />
        <div className="absolute inset-0 bg-gradient-to-t from-black/40 to-transparent pointer-events-none" />
      </div>
      {meta && (
        <div className="flex flex-wrap gap-3 text-xs text-slate-500">
          <span className="flex items-center gap-1">📐 {meta.w} × {meta.h}px</span>
          <span className="flex items-center gap-1">💾 {(file.size / 1024).toFixed(0)} KB</span>
          <span className="flex items-center gap-1">🖼️ {file.type || 'image'}</span>
        </div>
      )}
    </div>
  );
}

export default function FileUpload({ accept, label, hint, type = 'image', onFile, maxMB = 100 }) {
  const [dragging, setDragging] = useState(false);
  const [file, setFile]         = useState(null);
  const [error, setError]       = useState('');
  const inputRef = useRef(null);
  const Icon = FORMAT_ICON[type] || Upload;

  const handleFile = useCallback((f) => {
    setError('');
    if (!f) return;
    if (f.size > maxMB * 1024 * 1024) {
      setError(`File exceeds ${maxMB} MB limit.`);
      return;
    }
    setFile(f);
    onFile(f);
  }, [maxMB, onFile]);

  const onDrop = (e) => {
    e.preventDefault();
    setDragging(false);
    const f = e.dataTransfer.files?.[0];
    if (f) handleFile(f);
  };

  const clearFile = (e) => {
    e.stopPropagation();
    setFile(null);
    setError('');
    onFile(null);
    if (inputRef.current) inputRef.current.value = '';
  };

  return (
    <div>
      <label
        className={`upload-zone block ${dragging ? 'active' : ''} ${file ? 'border-primary-500/50 bg-primary-900/10' : ''}`}
        onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
        onDragLeave={() => setDragging(false)}
        onDrop={onDrop}
      >
        <input
          ref={inputRef}
          type="file"
          accept={accept}
          className="hidden"
          onChange={(e) => handleFile(e.target.files?.[0])}
        />

        {file ? (
          <div className="flex flex-col items-center gap-3">
            <div className="w-12 h-12 rounded-xl bg-emerald-600/20 border border-emerald-500/30 flex items-center justify-center">
              <FileCheck size={22} className="text-emerald-400" />
            </div>
            <div className="text-center">
              <p className="font-medium text-slate-200 text-sm truncate max-w-xs">{file.name}</p>
              <p className="text-slate-500 text-xs mt-0.5">{(file.size / 1024 / 1024).toFixed(2)} MB</p>
            </div>
            <button
              onClick={clearFile}
              className="flex items-center gap-1 text-slate-400 hover:text-red-400 text-xs transition-colors px-3 py-1.5 rounded-lg border border-surface-border hover:border-red-500/40"
            >
              <X size={12} /> Remove file
            </button>
          </div>
        ) : (
          <div className="flex flex-col items-center gap-4">
            <div className={`w-16 h-16 rounded-2xl bg-primary-600/10 border-2 border-dashed border-primary-500/30 flex items-center justify-center transition-all duration-300 ${dragging ? 'border-primary-400 bg-primary-600/20 scale-110' : ''}`}>
              {dragging ? (
                <Upload size={26} className="text-primary-300 animate-bounce" />
              ) : (
                <Icon size={26} className="text-primary-400" />
              )}
            </div>
            <div className="text-center">
              <p className="font-semibold text-slate-200">
                {dragging ? 'Drop it here!' : label}
              </p>
              <p className="text-slate-500 text-sm mt-1">{hint}</p>
              <p className="text-slate-600 text-xs mt-2">or <span className="text-primary-400 underline">browse files</span> · Max {maxMB} MB</p>
            </div>
          </div>
        )}
      </label>

      {/* Image preview */}
      {file && type === 'image' && <ImagePreview file={file} />}

      {error && <p className="text-red-400 text-xs mt-2 text-center">{error}</p>}
    </div>
  );
}
