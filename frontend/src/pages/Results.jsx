// pages/Results.jsx — enhanced with collapsible sections, share, and analyze-another
import { useState, useCallback } from 'react';
import { useLocation, useNavigate, Link } from 'react-router-dom';
import {
  ArrowLeft, Download, ExternalLink, Frame, BarChart2,
  Shield, AlertTriangle, CheckCircle, Info, ChevronDown,
  Share2, Plus, Copy, Check
} from 'lucide-react';
import TrustScoreCard from '../components/TrustScoreCard';
import EvidenceList from '../components/EvidenceList';
import ExplanationSection from '../components/ExplanationSection';
import { useToast } from '../context/ToastContext';

function MetaRow({ label, value, mono }) {
  if (value == null || value === '') return null;
  return (
    <div className="flex justify-between gap-4 py-2 border-b border-surface-border last:border-0">
      <span className="text-slate-500 text-sm">{label}</span>
      <span className={`text-slate-200 text-sm text-right ${mono ? 'font-mono' : 'font-medium'} truncate max-w-xs`}>
        {String(value)}
      </span>
    </div>
  );
}

function CollapsibleSection({ title, icon: Icon, defaultOpen = true, children }) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div className="card-glass overflow-hidden animate-slide-up">
      <button
        onClick={() => setOpen(o => !o)}
        className="w-full flex items-center justify-between px-6 py-4 hover:bg-white/5 transition-colors"
      >
        <div className="flex items-center gap-2">
          <Icon size={18} className="text-primary-400" />
          <h2 className="text-lg font-semibold text-slate-100">{title}</h2>
        </div>
        <ChevronDown
          size={16}
          className={`text-slate-400 transition-transform duration-300 ${open ? 'rotate-180' : ''}`}
        />
      </button>
      <div className={`accordion-content ${open ? 'open' : 'closed'}`}>
        <div className="px-6 pb-6 space-y-4">
          {children}
        </div>
      </div>
    </div>
  );
}

function ExternalIntelPanel({ ext }) {
  if (!ext) return null;
  const gsb = ext.google_safe_browsing || {};
  const vt  = ext.virustotal || {};
  const statusIcon = (status, good = 'ok') =>
    status === good
      ? <CheckCircle size={14} className="text-emerald-400" />
      : status === 'threat_found'
        ? <AlertTriangle size={14} className="text-red-400" />
        : <Info size={14} className="text-slate-500" />;

  return (
    <div className="space-y-3">
      <div className="flex items-start gap-3 bg-surface rounded-xl px-4 py-3">
        {statusIcon(gsb.status)}
        <div>
          <p className="text-slate-300 text-sm font-medium">Google Safe Browsing</p>
          <p className="text-slate-500 text-xs mt-0.5">{gsb.message || 'Not configured'}</p>
        </div>
      </div>
      <div className="flex items-start gap-3 bg-surface rounded-xl px-4 py-3">
        {statusIcon(vt.status)}
        <div>
          <p className="text-slate-300 text-sm font-medium">VirusTotal</p>
          <p className="text-slate-500 text-xs mt-0.5">{vt.message || 'Not configured'}</p>
          {vt.total > 0 && (
            <div className="flex gap-3 mt-1.5 text-xs">
              <span className="text-red-400">{vt.malicious} malicious</span>
              <span className="text-amber-400">{vt.suspicious} suspicious</span>
              <span className="text-emerald-400">{vt.harmless} harmless</span>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function FeatureTable({ features }) {
  if (!features || !Object.keys(features).length) return null;
  const entries = Object.entries(features).filter(([, v]) => typeof v === 'number');
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="text-left border-b border-surface-border">
            <th className="pb-2 text-slate-400 font-medium">Feature</th>
            <th className="pb-2 text-slate-400 font-medium text-right">Value</th>
          </tr>
        </thead>
        <tbody>
          {entries.map(([k, v]) => (
            <tr key={k} className="border-b border-surface-border/50 last:border-0">
              <td className="py-1.5 text-slate-400 font-mono text-xs">{k}</td>
              <td className="py-1.5 text-slate-200 text-right font-mono">{Number(v).toFixed(2)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function ShareButton({ result }) {
  const [copied, setCopied] = useState(false);
  const toast = useToast();

  const handleShare = useCallback(async () => {
    const summary = `TrustAI Analysis Result\nType: ${result.type}\nTrust Score: ${result.trust_score}/100\nRisk Level: ${result.risk_level}\nPrediction: ${result.prediction}\nID: ${result.analysis_id}`;
    try {
      await navigator.clipboard.writeText(summary);
      setCopied(true);
      toast.success('Copied to clipboard!', 'Share this result with your team');
      setTimeout(() => setCopied(false), 2000);
    } catch {
      toast.error('Copy failed', 'Could not access clipboard');
    }
  }, [result, toast]);

  return (
    <button onClick={handleShare} className="btn-secondary">
      {copied ? <Check size={15} className="text-emerald-400" /> : <Share2 size={15} />}
      {copied ? 'Copied!' : 'Share'}
    </button>
  );
}

export default function Results() {
  const { state } = useLocation();
  const navigate  = useNavigate();
  const result    = state?.result;

  if (!result) {
    return (
      <div className="max-w-lg mx-auto px-4 py-24 text-center space-y-4">
        <p className="text-slate-400">No result to display. Please run an analysis first.</p>
        <Link to="/" className="btn-primary inline-flex">Go Home</Link>
      </div>
    );
  }

  const typeLabel = { url: 'URL Analysis', image: 'Image Analysis', video: 'Video Analysis' };
  const analyzeAgainPath = { url: '/analyze/url', image: '/analyze/image', video: '/analyze/video' };

  const downloadJSON = () => {
    const blob = new Blob([JSON.stringify(result, null, 2)], { type: 'application/json' });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = `trustai-${result.analysis_id?.slice(0, 8)}.json`;
    a.click();
  };

  return (
    <main className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-12 space-y-6 animate-fade-in">
      {/* Top bar */}
      <div className="flex items-center justify-between flex-wrap gap-3">
        <button onClick={() => navigate(-1)} className="btn-secondary">
          <ArrowLeft size={15} /> Back
        </button>
        <div className="text-center">
          <h1 className="text-2xl font-bold text-white">{typeLabel[result.type] || 'Analysis Result'}</h1>
          <p className="text-slate-500 text-xs mt-0.5 font-mono">{result.analysis_id}</p>
        </div>
        <div className="flex items-center gap-2">
          <ShareButton result={result} />
          <button onClick={downloadJSON} className="btn-secondary">
            <Download size={15} /> JSON
          </button>
        </div>
      </div>

      {/* Main grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left: Score + Meta */}
        <div className="lg:col-span-1 space-y-5">
          <TrustScoreCard
            score={result.trust_score}
            riskLevel={result.risk_level}
            confidence={result.confidence}
            prediction={result.prediction}
          />

          {/* Quick meta */}
          <div className="card p-5 space-y-1">
            <MetaRow label="Analysis ID"   value={result.analysis_id?.slice(0, 16) + '…'} mono />
            <MetaRow label="Type"          value={result.type} />
            <MetaRow label="Created"       value={result.created_at ? new Date(result.created_at).toLocaleString() : null} />
            {result.type === 'url' && <MetaRow label="URL" value={result.url} mono />}
            {result.type === 'url' && <MetaRow label="Security Status" value={result.security_status} />}
            {result.type === 'url' && result.phishing_probability != null && (
              <MetaRow label="Phishing Probability" value={`${(result.phishing_probability * 100).toFixed(1)}%`} />
            )}
            {result.type === 'image' && result.ai_generated_probability != null && (
              <MetaRow label="AI-Generated Prob." value={`${(result.ai_generated_probability * 100).toFixed(1)}%`} />
            )}
            {result.type === 'video' && (
              <>
                <MetaRow label="Frames Analyzed"  value={result.frames_analyzed} />
                <MetaRow label="Suspicious Frames" value={result.suspicious_frames} />
                {result.suspicious_frame_ratio != null && (
                  <MetaRow label="Suspicious Ratio" value={`${(result.suspicious_frame_ratio * 100).toFixed(1)}%`} />
                )}
                {result.deepfake_probability != null && (
                  <MetaRow label="Deepfake Probability" value={`${(result.deepfake_probability * 100).toFixed(1)}%`} />
                )}
              </>
            )}
            {!result.model_available && (
              <div className="flex items-center gap-2 text-amber-400 text-xs pt-2">
                <AlertTriangle size={12} /> Model not trained yet
              </div>
            )}
          </div>

          {/* Analyze Another */}
          <Link
            to={analyzeAgainPath[result.type] || '/'}
            className="btn-primary w-full justify-center"
          >
            <Plus size={16} /> Analyze Another
          </Link>
        </div>

        {/* Right: Collapsible detail panels */}
        <div className="lg:col-span-2 space-y-4">
          <CollapsibleSection title="Explanation" icon={Shield} defaultOpen={true}>
            <ExplanationSection
              explanation={result.explanation}
              limitations={result.limitations}
            />
          </CollapsibleSection>

          <CollapsibleSection title="Evidence" icon={BarChart2} defaultOpen={true}>
            <EvidenceList evidence={result.evidence} />
          </CollapsibleSection>

          {result.type === 'url' && result.external_intelligence && (
            <CollapsibleSection title="External Security Intelligence" icon={ExternalLink} defaultOpen={true}>
              <ExternalIntelPanel ext={result.external_intelligence} />
            </CollapsibleSection>
          )}

          {result.type === 'url' && result.feature_values && (
            <CollapsibleSection title="URL Feature Details" icon={BarChart2} defaultOpen={false}>
              <FeatureTable features={result.feature_values} />
            </CollapsibleSection>
          )}

          {result.type === 'video' && result.technical_signals && (
            <CollapsibleSection title="Video Technical Signals" icon={Frame} defaultOpen={false}>
              <FeatureTable features={result.technical_signals} />
            </CollapsibleSection>
          )}
        </div>
      </div>
    </main>
  );
}
