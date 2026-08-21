// pages/AnalyzeImage.jsx
import { useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { Image, Scan, ShieldAlert, CheckCircle, Cpu, BarChart2 } from 'lucide-react';
import { analyzeImage } from '../services/api';
import FileUpload from '../components/FileUpload';
import { useToast } from '../context/ToastContext';

const STAGES = [
  { id: 'upload',  label: 'Uploading image',         icon: Image },
  { id: 'analyze', label: 'Running vision model',    icon: Cpu },
  { id: 'score',   label: 'Computing Trust Score',   icon: BarChart2 },
  { id: 'done',    label: 'Generating report',        icon: CheckCircle },
];

function AnalysisSteps({ stage }) {
  const idx = STAGES.findIndex(s => s.id === stage);
  return (
    <div className="card-glass p-8 max-w-lg mx-auto space-y-6 animate-fade-in">
      <div className="text-center space-y-2">
        <div className="inline-flex w-16 h-16 rounded-2xl bg-gradient-to-br from-violet-500 to-purple-600 items-center justify-center shadow-lg shadow-purple-900/40 mx-auto">
          <Image size={28} className="text-white" />
        </div>
        <h2 className="text-xl font-bold text-white">Analyzing Image…</h2>
        <p className="text-slate-400 text-sm">Our ML pipeline is processing your file</p>
      </div>

      <div className="space-y-3">
        {STAGES.map((s, i) => {
          const Icon = s.icon;
          const done    = i < idx;
          const active  = i === idx;
          const pending = i > idx;
          return (
            <div
              key={s.id}
              className={`flex items-center gap-4 p-4 rounded-xl border transition-all duration-500 ${
                active  ? 'border-primary-500/50 bg-primary-900/30' :
                done    ? 'border-emerald-500/30 bg-emerald-900/10' :
                          'border-surface-border bg-surface-card/30'
              }`}
            >
              <div className={`w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0 ${
                active  ? 'step-active' :
                done    ? 'step-done' :
                          'step-pending'
              }`}>
                {done
                  ? <CheckCircle size={14} />
                  : active
                    ? <Icon size={14} className="animate-pulse" />
                    : <Icon size={14} />
                }
              </div>
              <span className={`text-sm font-medium ${
                active ? 'text-primary-300' : done ? 'text-emerald-400' : 'text-slate-500'
              }`}>
                {s.label}
                {active && <span className="ml-2 inline-block animate-pulse">…</span>}
              </span>
            </div>
          );
        })}
      </div>

      {/* Shimmer bar */}
      <div className="h-1 w-full bg-surface rounded-full overflow-hidden">
        <div
          className="h-full bg-gradient-to-r from-violet-500 to-primary-400 transition-all duration-700 rounded-full"
          style={{ width: `${((idx + 1) / STAGES.length) * 100}%` }}
        />
      </div>
    </div>
  );
}

export default function AnalyzeImage() {
  const [file, setFile]         = useState(null);
  const [loading, setLoading]   = useState(false);
  const [stage, setStage]       = useState('upload');
  const [error, setError]       = useState('');
  const navigate = useNavigate();
  const toast    = useToast();

  const submit = useCallback(async (e) => {
    e.preventDefault();
    if (!file) { setError('Please select an image to upload.'); return; }
    setError('');
    setLoading(true);
    setStage('upload');
    try {
      const result = await analyzeImage(file, (evt) => {
        if (evt.total) {
          const pct = (evt.loaded / evt.total) * 100;
          if (pct < 50) setStage('upload');
          else setStage('analyze');
        }
      });
      setStage('score');
      await new Promise(r => setTimeout(r, 400));
      setStage('done');
      await new Promise(r => setTimeout(r, 300));
      toast.success('Analysis complete!', `Trust Score: ${result.trust_score}/100`);
      navigate('/results', { state: { result } });
    } catch (err) {
      setError(err.message || 'Analysis failed. Please try again.');
      toast.error('Analysis failed', err.message);
    } finally {
      setLoading(false);
    }
  }, [file, navigate, toast]);

  if (loading) return (
    <div className="max-w-lg mx-auto px-4 py-24">
      <AnalysisSteps stage={stage} />
    </div>
  );

  return (
    <main className="max-w-2xl mx-auto px-4 sm:px-6 py-16 space-y-8 animate-fade-in">
      {/* Header */}
      <div className="text-center space-y-3">
        <div className="inline-flex w-16 h-16 rounded-2xl bg-gradient-to-br from-violet-500 to-purple-600
                        items-center justify-center shadow-lg shadow-purple-900/40 mx-auto">
          <Image size={28} className="text-white" />
        </div>
        <h1 className="text-3xl font-bold text-white">Image Detection</h1>
        <p className="text-slate-400 text-sm leading-relaxed max-w-md mx-auto">
          Upload an image to detect AI-generated content or image manipulation using vision ML models.
        </p>
      </div>

      {/* Form */}
      <div className="card-glass p-8 space-y-6">
        <form onSubmit={submit} className="space-y-5">
          <FileUpload
            accept="image/jpeg,image/png,image/webp,image/bmp,image/tiff"
            label="Drag & drop an image here"
            hint="Supported: JPG, PNG, WEBP, BMP, TIFF"
            type="image"
            maxMB={10}
            onFile={setFile}
          />

          {error && (
            <div className="flex items-center gap-2 text-red-400 text-sm bg-red-900/20 border border-red-800/30 rounded-xl px-4 py-3">
              <ShieldAlert size={15} /> {error}
            </div>
          )}

          <button
            type="submit"
            id="analyze-image-btn"
            className="btn-primary w-full justify-center text-base py-3.5"
            disabled={!file}
          >
            <Scan size={18} /> Analyze Image
          </button>
        </form>
      </div>

      {/* Info */}
      <div className="card p-5 space-y-2 text-sm text-slate-400">
        <p className="font-medium text-slate-300">What we analyze:</p>
        <ul className="space-y-1">
          {[
            'EfficientNet-B0 AI-generation classification',
            'EXIF metadata availability & forensic signals',
            'Image dimensions, format and compression signals',
            'Model confidence calibration',
          ].map(item => (
            <li key={item} className="flex gap-2"><span className="text-primary-500">→</span>{item}</li>
          ))}
        </ul>
        <p className="text-xs text-slate-500 pt-2">
          Note: Image model must be trained before inference is available. See README.
        </p>
      </div>
    </main>
  );
}
