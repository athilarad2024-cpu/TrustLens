// pages/AnalyzeURL.jsx
import { useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { Link2, Search, ShieldAlert, ExternalLink, CheckCircle, Cpu, BarChart2 } from 'lucide-react';
import { analyzeUrl } from '../services/api';
import { useToast } from '../context/ToastContext';

const EXAMPLE_URLS = [
  'https://google.com',
  'https://github.com/openai/gpt-4',
  'http://paypal-verify-account.xyz/login',
];

const STAGES = [
  { id: 'parse',   label: 'Parsing URL structure',     icon: Link2 },
  { id: 'ml',      label: 'Running phishing model',    icon: Cpu },
  { id: 'intel',   label: 'Querying threat intel',     icon: ExternalLink },
  { id: 'score',   label: 'Computing Trust Score',     icon: BarChart2 },
];

function URLAnalysisProgress({ stage }) {
  const idx = STAGES.findIndex(s => s.id === stage);
  return (
    <div className="card-glass p-8 max-w-md mx-auto space-y-6 animate-fade-in">
      <div className="text-center space-y-2">
        <div className="inline-flex w-16 h-16 rounded-2xl bg-gradient-to-br from-emerald-500 to-teal-600 items-center justify-center shadow-lg shadow-emerald-900/40 mx-auto">
          <Link2 size={28} className="text-white" />
        </div>
        <h2 className="text-xl font-bold text-white">Analyzing URL…</h2>
      </div>
      <div className="space-y-2">
        {STAGES.map((s, i) => {
          const Icon = s.icon;
          const done   = i < idx;
          const active = i === idx;
          return (
            <div key={s.id} className={`flex items-center gap-3 p-3 rounded-xl border transition-all duration-500 ${
              active  ? 'border-emerald-500/50 bg-emerald-900/20' :
              done    ? 'border-emerald-500/20 bg-emerald-900/10' :
                        'border-surface-border/30'
            }`}>
              <div className={`w-7 h-7 rounded-lg flex items-center justify-center flex-shrink-0 ${
                active ? 'bg-emerald-600 text-white' :
                done   ? 'bg-emerald-600/30 text-emerald-400' :
                         'bg-surface-card text-slate-500'
              }`}>
                {done ? <CheckCircle size={13} /> : <Icon size={13} className={active ? 'animate-pulse' : ''} />}
              </div>
              <span className={`text-sm ${active ? 'text-emerald-300' : done ? 'text-emerald-400' : 'text-slate-500'}`}>
                {s.label}{active && <span className="animate-pulse ml-1">…</span>}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
}

export default function AnalyzeURL() {
  const [url, setUrl]       = useState('');
  const [loading, setLoading] = useState(false);
  const [stage, setStage]   = useState('parse');
  const [error, setError]   = useState('');
  const navigate = useNavigate();
  const toast    = useToast();

  const submit = useCallback(async (e) => {
    e.preventDefault();
    if (!url.trim()) { setError('Please enter a URL.'); return; }
    setError('');
    setLoading(true);
    setStage('parse');
    // Simulate stage progression during the real async call
    const stageTimer1 = setTimeout(() => setStage('ml'),    600);
    const stageTimer2 = setTimeout(() => setStage('intel'), 1500);
    const stageTimer3 = setTimeout(() => setStage('score'), 2500);
    try {
      const result = await analyzeUrl(url.trim());
      clearTimeout(stageTimer1); clearTimeout(stageTimer2); clearTimeout(stageTimer3);
      setStage('score');
      await new Promise(r => setTimeout(r, 300));
      toast.success('URL analyzed!', `Trust Score: ${result.trust_score}/100 — ${result.risk_level} risk`);
      navigate('/results', { state: { result } });
    } catch (err) {
      clearTimeout(stageTimer1); clearTimeout(stageTimer2); clearTimeout(stageTimer3);
      setError(err.message || 'Analysis failed. Please try again.');
      toast.error('Analysis failed', err.message);
    } finally {
      setLoading(false);
    }
  }, [url, navigate, toast]);

  if (loading) return (
    <div className="max-w-lg mx-auto px-4 py-24">
      <URLAnalysisProgress stage={stage} />
    </div>
  );

  return (
    <main className="max-w-2xl mx-auto px-4 sm:px-6 py-16 space-y-8 animate-fade-in">
      {/* Header */}
      <div className="text-center space-y-3">
        <div className="inline-flex w-16 h-16 rounded-2xl bg-gradient-to-br from-emerald-500 to-teal-600
                        items-center justify-center shadow-lg shadow-emerald-900/40 mx-auto">
          <Link2 size={28} className="text-white" />
        </div>
        <h1 className="text-3xl font-bold text-white">URL Phishing Detection</h1>
        <p className="text-slate-400 text-sm leading-relaxed max-w-md mx-auto">
          Enter a URL to analyze it for phishing signals, suspicious structure, and external threat intelligence.
        </p>
      </div>

      {/* Form */}
      <div className="card-glass p-8 space-y-6">
        <form onSubmit={submit} className="space-y-4">
          <div>
            <label className="label">URL to analyze</label>
            <div className="relative">
              <Link2 size={16} className="absolute left-4 top-1/2 -translate-y-1/2 text-slate-500" />
              <input
                id="url-input"
                type="url"
                className="input-field pl-10 pr-4"
                placeholder="https://example.com/page"
                value={url}
                onChange={(e) => setUrl(e.target.value)}
                autoFocus
              />
            </div>
          </div>

          {error && (
            <div className="flex items-center gap-2 text-red-400 text-sm bg-red-900/20 border border-red-800/30 rounded-xl px-4 py-3">
              <ShieldAlert size={15} /> {error}
            </div>
          )}

          <button type="submit" id="analyze-url-btn" className="btn-primary w-full justify-center text-base py-3.5">
            <Search size={18} /> Analyze URL
          </button>
        </form>

        {/* Examples */}
        <div>
          <p className="text-xs text-slate-500 mb-2">Try an example:</p>
          <div className="flex flex-wrap gap-2">
            {EXAMPLE_URLS.map(ex => (
              <button
                key={ex}
                onClick={() => setUrl(ex)}
                className="text-xs font-mono text-slate-400 bg-surface px-3 py-1.5 rounded-lg
                           hover:bg-primary-900/30 hover:text-primary-300 border border-surface-border
                           transition-colors max-w-full truncate"
              >
                {ex}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Info */}
      <div className="card p-5 space-y-2 text-sm text-slate-400">
        <p className="font-medium text-slate-300">What we analyze:</p>
        <ul className="space-y-1 list-none">
          {[
            'URL structure & suspicious character patterns',
            'Machine learning phishing classifier',
            'Google Safe Browsing (if configured)',
            'VirusTotal threat intelligence (if configured)',
          ].map(item => (
            <li key={item} className="flex gap-2"><span className="text-primary-500">→</span>{item}</li>
          ))}
        </ul>
      </div>
    </main>
  );
}
