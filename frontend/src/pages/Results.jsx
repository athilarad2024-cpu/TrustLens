// pages/Results.jsx — Enhanced with Gemini Multimodal AI & Forensics Visualizations
import { useState, useCallback } from 'react';
import { useLocation, useNavigate, Link } from 'react-router-dom';
import {
  ArrowLeft, Download, ExternalLink, Frame, BarChart2,
  Shield, AlertTriangle, CheckCircle, Info, ChevronDown,
  Share2, Plus, Check, Sparkles, Eye, Film, Layers, HelpCircle
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

function CollapsibleSection({ title, icon: Icon, defaultOpen = true, badge, children }) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <div className="card-glass overflow-hidden animate-slide-up">
      <button
        onClick={() => setOpen(o => !o)}
        className="w-full flex items-center justify-between px-6 py-4 hover:bg-white/5 transition-colors"
      >
        <div className="flex items-center gap-2.5">
          <Icon size={18} className="text-primary-400" />
          <h2 className="text-lg font-semibold text-slate-100">{title}</h2>
          {badge && (
            <span className="px-2 py-0.5 text-xs font-medium rounded-full bg-primary-900/60 text-primary-300 border border-primary-500/30">
              {badge}
            </span>
          )}
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

function ReasonsPanel({ reasons }) {
  if (!reasons || !reasons.length) return null;
  return (
    <div className="space-y-2.5">
      {reasons.map((reason, idx) => (
        <div key={idx} className="flex items-start gap-3 bg-surface/60 border border-surface-border rounded-xl px-4 py-3">
          <div className="w-5 h-5 rounded-full bg-primary-500/20 text-primary-400 flex items-center justify-center flex-shrink-0 mt-0.5 text-xs font-bold">
            {idx + 1}
          </div>
          <p className="text-slate-300 text-sm leading-relaxed">{reason}</p>
        </div>
      ))}
    </div>
  );
}

function VisualSignalsPanel({ signals }) {
  if (!signals || !signals.length) return null;

  const assessmentBadge = (assess) => {
    if (assess === 'synthetic') {
      return <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-rose-900/40 text-rose-300 border border-rose-500/30">Synthetic</span>;
    }
    if (assess === 'natural') {
      return <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-900/40 text-emerald-300 border border-emerald-500/30">Natural</span>;
    }
    return <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-amber-900/40 text-amber-300 border border-amber-500/30">Inconclusive</span>;
  };

  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
      {signals.map((sig, idx) => (
        <div key={idx} className="bg-surface/50 border border-surface-border rounded-xl p-4 space-y-2">
          <div className="flex items-center justify-between">
            <span className="text-xs font-semibold uppercase tracking-wider text-slate-400 font-mono">
              {sig.feature || 'Visual Feature'}
            </span>
            {assessmentBadge(sig.assessment)}
          </div>
          <p className="text-slate-300 text-sm">{sig.observation}</p>
        </div>
      ))}
    </div>
  );
}

function TemporalSignalsPanel({ signals, consistencyScore }) {
  return (
    <div className="space-y-4">
      {consistencyScore != null && (
        <div className="flex items-center justify-between p-4 bg-primary-950/40 border border-primary-500/20 rounded-xl">
          <div>
            <p className="text-sm font-semibold text-primary-200">Temporal Consistency Index</p>
            <p className="text-xs text-slate-400 mt-0.5">Smoothness and identity stability across video duration</p>
          </div>
          <div className="text-right">
            <span className="text-2xl font-bold text-primary-300 font-mono">
              {(consistencyScore * 100).toFixed(0)}%
            </span>
          </div>
        </div>
      )}

      {signals && signals.length > 0 && (
        <div className="space-y-2">
          {signals.map((sig, idx) => (
            <div key={idx} className="flex items-start justify-between gap-3 p-3.5 bg-surface/50 border border-surface-border rounded-xl">
              <div className="space-y-1">
                <span className="text-xs font-semibold uppercase tracking-wider text-slate-400 font-mono">
                  {sig.signal || 'Temporal Observation'}
                </span>
                <p className="text-slate-300 text-sm">{sig.observation}</p>
              </div>
              <span className={`px-2.5 py-0.5 rounded-full text-xs font-semibold flex-shrink-0 ${
                sig.is_suspicious
                  ? 'bg-rose-900/40 text-rose-300 border border-rose-500/30'
                  : 'bg-emerald-900/40 text-emerald-300 border border-emerald-500/30'
              }`}>
                {sig.is_suspicious ? 'Warping/Jitter' : 'Stable'}
              </span>
            </div>
          ))}
        </div>
      )}
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
  const entries = Object.entries(features).filter(([, v]) => typeof v === 'number' || typeof v === 'string' || typeof v === 'boolean');
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="text-left border-b border-surface-border">
            <th className="pb-2 text-slate-400 font-medium">Metric / Feature</th>
            <th className="pb-2 text-slate-400 font-medium text-right">Value</th>
          </tr>
        </thead>
        <tbody>
          {entries.map(([k, v]) => (
            <tr key={k} className="border-b border-surface-border/50 last:border-0">
              <td className="py-1.5 text-slate-400 font-mono text-xs">{k}</td>
              <td className="py-1.5 text-slate-200 text-right font-mono">
                {typeof v === 'number' ? Number(v).toFixed(3) : String(v)}
              </td>
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
    const summary = `TrustAI Analysis Result\nType: ${result.type}\nTrust Score: ${result.trust_score}/100\nClassification: ${result.classification || result.prediction}\nConfidence: ${Math.round((result.confidence || 0.6) * 100)}%\nID: ${result.analysis_id}`;
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

  const typeLabel = { url: 'URL Analysis', image: 'Image AI Analysis', video: 'Video Deepfake Analysis' };
  const analyzeAgainPath = { url: '/analyze/url', image: '/analyze/image', video: '/analyze/video' };

  const downloadJSON = () => {
    const blob = new Blob([JSON.stringify(result, null, 2)], { type: 'application/json' });
    const a = document.createElement('a');
    a.href = URL.createObjectURL(blob);
    a.download = `trustai-${result.analysis_id?.slice(0, 8)}.json`;
    a.click();
  };

  const aiProb = result.ai_probability ?? result.ai_generated_probability ?? result.deepfake_probability;
  const classification = result.classification || result.prediction;

  return (
    <main className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8 py-12 space-y-6 animate-fade-in">
      {/* Top bar */}
      <div className="flex items-center justify-between flex-wrap gap-3">
        <button onClick={() => navigate(-1)} className="btn-secondary">
          <ArrowLeft size={15} /> Back
        </button>
        <div className="text-center">
          <div className="inline-flex items-center gap-2">
            <h1 className="text-2xl font-bold text-white">{typeLabel[result.type] || 'Analysis Result'}</h1>
            {result.gemini_available && (
              <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-violet-900/50 text-violet-300 border border-violet-500/30">
                <Sparkles size={11} /> Gemini 2.5 Vision
              </span>
            )}
          </div>
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
            prediction={classification}
            aiProbability={aiProb}
          />

          {/* Quick meta */}
          <div className="card p-5 space-y-1">
            <MetaRow label="Classification" value={classification ? classification.replace(/_/g, ' ') : 'Uncertain'} />
            {aiProb != null && (
              <MetaRow label="AI-Generated Probability" value={`${(aiProb * 100).toFixed(1)}%`} />
            )}
            {result.confidence != null && (
              <MetaRow label="Confidence" value={`${Math.round(result.confidence * 100)}%`} />
            )}
            <MetaRow label="Type" value={result.type} />
            <MetaRow label="Created" value={result.created_at ? new Date(result.created_at).toLocaleString() : null} />

            {result.type === 'url' && <MetaRow label="URL" value={result.url} mono />}
            {result.type === 'url' && <MetaRow label="Security Status" value={result.security_status} />}

            {result.type === 'video' && (
              <>
                <MetaRow label="Frames Sampled" value={result.frames_analyzed} />
                {result.temporal_consistency_score != null && (
                  <MetaRow label="Temporal Consistency" value={`${(result.temporal_consistency_score * 100).toFixed(0)}%`} />
                )}
              </>
            )}

            <div className="pt-2 border-t border-surface-border flex items-center justify-between text-xs text-slate-400">
              <span>Gemini Multimodal</span>
              <span className={result.gemini_available ? "text-emerald-400 font-medium" : "text-slate-500"}>
                {result.gemini_available ? "Active & Calibrated" : "Fallback (Local)"}
              </span>
            </div>
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
          {/* Reasons Panel */}
          {result.reasons && result.reasons.length > 0 && (
            <CollapsibleSection title="Key Findings & Reasoning" icon={Sparkles} defaultOpen={true}>
              <ReasonsPanel reasons={result.reasons} />
            </CollapsibleSection>
          )}

          {/* Visual Signals Panel (for image/video) */}
          {result.visual_signals && result.visual_signals.length > 0 && (
            <CollapsibleSection title="Visual Signal Inspections" icon={Eye} defaultOpen={true} badge={`${result.visual_signals.length} checks`}>
              <VisualSignalsPanel signals={result.visual_signals} />
            </CollapsibleSection>
          )}

          {/* Temporal Signals Panel (for video) */}
          {result.type === 'video' && (
            <CollapsibleSection title="Temporal Consistency & Motion" icon={Film} defaultOpen={true}>
              <TemporalSignalsPanel
                signals={result.temporal_signals}
                consistencyScore={result.temporal_consistency_score}
              />
            </CollapsibleSection>
          )}

          {/* Explanation Section */}
          <CollapsibleSection title="Explanation & Summary" icon={Shield} defaultOpen={true}>
            <ExplanationSection
              explanation={result.explanation}
              limitations={result.limitations}
            />
          </CollapsibleSection>

          {/* Evidence List */}
          <CollapsibleSection title="Forensic & Multimodal Evidence" icon={BarChart2} defaultOpen={true} badge={`${result.evidence?.length || 0} items`}>
            <EvidenceList evidence={result.evidence} />
          </CollapsibleSection>

          {/* External Intelligence (URL) */}
          {result.type === 'url' && result.external_intelligence && (
            <CollapsibleSection title="External Security Intelligence" icon={ExternalLink} defaultOpen={true}>
              <ExternalIntelPanel ext={result.external_intelligence} />
            </CollapsibleSection>
          )}

          {/* Technical signals / features */}
          {result.technical_signals && (
            <CollapsibleSection title="Technical Signal Metrics" icon={Layers} defaultOpen={false}>
              <FeatureTable features={result.technical_signals} />
            </CollapsibleSection>
          )}
        </div>
      </div>
    </main>
  );
}
