// pages/AnalyzeVideo.jsx
import { useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { Video, Scan, ShieldAlert, Upload, Frame, Cpu, BarChart2, CheckCircle, Clock } from 'lucide-react';
import { analyzeVideo } from '../services/api';
import FileUpload from '../components/FileUpload';
import { useToast } from '../context/ToastContext';

const STAGES = [
  { id: 'upload',  label: 'Uploading video',              desc: 'Transferring file to analysis server',        icon: Upload },
  { id: 'sample',  label: 'Representative Frame Sampling', desc: 'Extracting keyframes across video duration',  icon: Frame },
  { id: 'analyze', label: 'Gemini Multimodal & Forensics', desc: 'Analyzing facial, visual & temporal flow',   icon: Cpu },
  { id: 'score',   label: 'Computing Trust Score',        desc: 'Calibrating confidence & uncertainty range',  icon: BarChart2 },
  { id: 'done',    label: 'Generating report',             desc: 'Building evidence & explanations',            icon: CheckCircle },
];

function VideoAnalysisProgress({ stage, uploadPct }) {
  const idx = STAGES.findIndex(s => s.id === stage);
  const pct = Math.round(((idx + (stage === 'upload' ? uploadPct / 100 : 1)) / STAGES.length) * 100);

  return (
    <div className="card-glass p-8 max-w-xl mx-auto space-y-6 animate-fade-in">
      <div className="text-center space-y-2">
        <div className="inline-flex w-16 h-16 rounded-2xl bg-gradient-to-br from-sky-500 to-blue-600 items-center justify-center shadow-lg shadow-blue-900/40 mx-auto">
          <Video size={28} className="text-white" />
        </div>
        <h2 className="text-xl font-bold text-white">Analyzing Video…</h2>
        <p className="text-slate-400 text-sm">Video analysis can take 30–120 seconds depending on file size</p>
      </div>

      {/* Progress bar */}
      <div className="space-y-2">
        <div className="flex justify-between text-xs text-slate-500">
          <span>Progress</span>
          <span>{pct}%</span>
        </div>
        <div className="h-2 bg-surface rounded-full overflow-hidden">
          <div
            className="h-full bg-gradient-to-r from-sky-500 to-blue-400 rounded-full transition-all duration-700"
            style={{ width: `${pct}%` }}
          />
        </div>
      </div>

      {/* Pipeline steps */}
      <div className="space-y-2">
        {STAGES.map((s, i) => {
          const Icon = s.icon;
          const done    = i < idx;
          const active  = i === idx;
          const pending = i > idx;
          return (
            <div
              key={s.id}
              className={`flex items-center gap-4 p-3.5 rounded-xl border transition-all duration-500 ${
                active  ? 'border-sky-500/50 bg-sky-900/20' :
                done    ? 'border-emerald-500/30 bg-emerald-900/10' :
                          'border-surface-border/30 bg-surface-card/20'
              }`}
            >
              <div className={`w-8 h-8 rounded-lg flex items-center justify-center flex-shrink-0 text-xs ${
                active  ? 'bg-sky-600 border border-sky-500 text-white' :
                done    ? 'bg-emerald-600/30 border border-emerald-500 text-emerald-400' :
                          'bg-surface-card border border-surface-border text-slate-500'
              }`}>
                {done
                  ? <CheckCircle size={14} />
                  : active
                    ? <Icon size={14} className="animate-pulse" />
                    : <Icon size={14} />
                }
              </div>
              <div className="flex-1 min-w-0">
                <p className={`text-sm font-medium ${
                  active ? 'text-sky-300' : done ? 'text-emerald-400' : 'text-slate-500'
                }`}>
                  {s.label}
                  {active && <span className="ml-1 animate-pulse">…</span>}
                </p>
                {active && <p className="text-xs text-slate-500 mt-0.5">{s.desc}</p>}
              </div>
              {/* Upload sub-progress */}
              {active && stage === 'upload' && uploadPct > 0 && (
                <span className="text-xs text-sky-400 font-mono flex-shrink-0">{Math.round(uploadPct)}%</span>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

export default function AnalyzeVideo() {
  const [file, setFile]       = useState(null);
  const [loading, setLoading] = useState(false);
  const [stage, setStage]     = useState('upload');
  const [uploadPct, setUploadPct] = useState(0);
  const [error, setError]     = useState('');
  const navigate = useNavigate();
  const toast    = useToast();

  const submit = useCallback(async (e) => {
    e.preventDefault();
    if (!file) { setError('Please select a video to upload.'); return; }
    setError('');
    setLoading(true);
    setStage('upload');
    setUploadPct(0);
    try {
      const result = await analyzeVideo(file, (evt) => {
        if (evt.total) {
          const pct = (evt.loaded / evt.total) * 100;
          setUploadPct(pct);
          if (pct >= 100) {
            setTimeout(() => setStage('sample'), 200);
            setTimeout(() => setStage('analyze'), 2000);
          }
        }
      });
      setStage('score');
      await new Promise(r => setTimeout(r, 500));
      setStage('done');
      await new Promise(r => setTimeout(r, 300));
      toast.success('Video analyzed!', `Trust Score: ${result.trust_score}/100`);
      navigate('/results', { state: { result } });
    } catch (err) {
      setError(err.message || 'Analysis failed. Please try again.');
      toast.error('Analysis failed', err.message);
    } finally {
      setLoading(false);
    }
  }, [file, navigate, toast]);

  if (loading) return (
    <div className="max-w-xl mx-auto px-4 py-16">
      <VideoAnalysisProgress stage={stage} uploadPct={uploadPct} />
    </div>
  );

  return (
    <main className="max-w-2xl mx-auto px-4 sm:px-6 py-16 space-y-8 animate-fade-in">
      {/* Header */}
      <div className="text-center space-y-3">
        <div className="inline-flex w-16 h-16 rounded-2xl bg-gradient-to-br from-sky-500 to-blue-600
                        items-center justify-center shadow-lg shadow-blue-900/40 mx-auto">
          <Video size={28} className="text-white" />
        </div>
        <h1 className="text-3xl font-bold text-white">Deepfake Detection</h1>
        <p className="text-slate-400 text-sm leading-relaxed max-w-md mx-auto">
          Upload a video to detect face manipulation and deepfake signals across sampled frames.
        </p>
      </div>

      {/* Warning banner */}
      <div className="flex items-start gap-3 bg-amber-900/20 border border-amber-800/30 rounded-xl px-4 py-3">
        <Clock size={16} className="text-amber-400 flex-shrink-0 mt-0.5" />
        <p className="text-amber-300 text-sm">
          Video analysis takes longer than image/URL analysis. Large files may take 30–120 seconds.
        </p>
      </div>

      {/* Form */}
      <div className="card-glass p-8 space-y-6">
        <form onSubmit={submit} className="space-y-5">
          <FileUpload
            accept="video/mp4,video/x-msvideo,video/quicktime,video/x-matroska,video/webm"
            label="Drag & drop a video here"
            hint="Supported: MP4, AVI, MOV, MKV, WEBM"
            type="video"
            maxMB={100}
            onFile={setFile}
          />

          {error && (
            <div className="flex items-center gap-2 text-red-400 text-sm bg-red-900/20 border border-red-800/30 rounded-xl px-4 py-3">
              <ShieldAlert size={15} /> {error}
            </div>
          )}

          <button
            type="submit"
            id="analyze-video-btn"
            className="btn-primary w-full justify-center text-base py-3.5"
            disabled={!file}
          >
            <Scan size={18} /> Analyze Video
          </button>
        </form>
      </div>

      {/* Pipeline info */}
      <div className="card p-5 space-y-2 text-sm text-slate-400">
        <p className="font-medium text-slate-300">Pipeline:</p>
        <ul className="space-y-1">
          {[
            'Sample up to 40 frames evenly from the video',
            'Detect and crop faces using Haar cascade',
            'Run EfficientNet-B0 frame-level deepfake classifier',
            'Aggregate frame scores (mean + suspicious-frame ratio)',
          ].map(item => (
            <li key={item} className="flex gap-2"><span className="text-primary-500">→</span>{item}</li>
          ))}
        </ul>
        <p className="text-xs text-slate-500 pt-2">
          Requires trained deepfake model. Analysis is limited if no faces are detected.
        </p>
      </div>
    </main>
  );
}
