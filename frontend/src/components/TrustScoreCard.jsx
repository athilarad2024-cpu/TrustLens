// components/TrustScoreCard.jsx
// Animated SVG ring displaying the 0-100 Trust Score.
import { useEffect, useRef } from 'react';

const RADIUS = 64;
const CIRCUMFERENCE = 2 * Math.PI * RADIUS;

function scoreColor(score) {
  if (score >= 80) return { stroke: '#10b981', text: 'text-emerald-400', glow: 'rgba(16,185,129,0.3)' };
  if (score >= 60) return { stroke: '#14b8a6', text: 'text-teal-400',    glow: 'rgba(20,184,166,0.3)' };
  if (score >= 40) return { stroke: '#f59e0b', text: 'text-amber-400',   glow: 'rgba(245,158,11,0.3)' };
  if (score >= 20) return { stroke: '#f97316', text: 'text-orange-400',  glow: 'rgba(249,115,22,0.3)' };
  return              { stroke: '#ef4444', text: 'text-red-400',      glow: 'rgba(239,68,68,0.3)' };
}

function riskLabel(risk) {
  const map = {
    'low':          'Low Risk',
    'moderate-low': 'Moderate-Low Risk',
    'medium':       'Medium Risk',
    'high':         'High Risk',
    'very-high':    'Very High Risk',
    'safe':         'Verified Safe',
  };
  return map[risk] || risk;
}

function badgeClass(risk) {
  const map = {
    'low':          'badge-low',
    'moderate-low': 'badge-mod-low',
    'medium':       'badge-medium',
    'high':         'badge-high',
    'very-high':    'badge-very-high',
    'safe':         'bg-emerald-950/80 text-emerald-300 border border-emerald-500/40',
  };
  return (map[risk] || 'badge-medium') + ' px-3 py-1 rounded-full text-xs font-semibold';
}

function classificationBadge(pred) {
  if (!pred) return null;
  const p = pred.toLowerCase().replace(/_/g, ' ');
  if (p.includes('authentic') || p.includes('safe') || p.includes('benign')) {
    return 'bg-emerald-900/40 text-emerald-300 border border-emerald-500/30';
  }
  if (p.includes('uncertain') || p.includes('moderate') || p.includes('suspicious')) {
    return 'bg-amber-900/40 text-amber-300 border border-amber-500/30';
  }
  return 'bg-rose-900/40 text-rose-300 border border-rose-500/30';
}

export default function TrustScoreCard({ score, riskLevel, confidence, prediction, aiProbability }) {
  const progressRef = useRef(null);
  const colors = scoreColor(score ?? 50);
  const dashOffset = CIRCUMFERENCE * (1 - (score ?? 0) / 100);

  useEffect(() => {
    if (!progressRef.current) return;
    // Reset then animate
    progressRef.current.style.strokeDashoffset = CIRCUMFERENCE;
    const id = setTimeout(() => {
      progressRef.current.style.strokeDashoffset = dashOffset;
    }, 50);
    return () => clearTimeout(id);
  }, [score, dashOffset]);

  return (
    <div className="card-glass p-8 flex flex-col items-center gap-6 animate-fade-in">
      {/* Score ring */}
      <div className="relative" style={{ filter: `drop-shadow(0 0 24px ${colors.glow})` }}>
        <svg width="160" height="160" viewBox="0 0 160 160">
          {/* Track */}
          <circle cx="80" cy="80" r={RADIUS}
            fill="none" stroke="#1e293b" strokeWidth="10" />
          {/* Progress */}
          <circle
            ref={progressRef}
            cx="80" cy="80" r={RADIUS}
            fill="none"
            stroke={colors.stroke}
            strokeWidth="10"
            strokeLinecap="round"
            strokeDasharray={CIRCUMFERENCE}
            strokeDashoffset={CIRCUMFERENCE}
            className="score-ring-progress"
            style={{ transform: 'rotate(-90deg)', transformOrigin: '80px 80px' }}
          />
        </svg>
        {/* Center text */}
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <span className={`text-4xl font-bold ${colors.text}`}>{score ?? '—'}</span>
          <span className="text-slate-500 text-xs mt-0.5">/ 100</span>
        </div>
      </div>

      {/* Badges and classification */}
      <div className="text-center space-y-3 w-full flex flex-col items-center">
        <div className="flex items-center gap-2 flex-wrap justify-center">
          <span className={badgeClass(riskLevel)}>{riskLabel(riskLevel)}</span>
          {prediction && (
            <span className={`px-3 py-1 rounded-full text-xs font-semibold uppercase tracking-wider ${classificationBadge(prediction)}`}>
              {prediction.replace(/_/g, ' ')}
            </span>
          )}
        </div>

        {/* AI Probability Bar (if present) */}
        {aiProbability != null && (
          <div className="w-52 pt-1">
            <div className="flex justify-between text-xs text-slate-400 mb-1">
              <span>AI Probability</span>
              <span className="font-mono font-semibold text-slate-200">{(aiProbability * 100).toFixed(1)}%</span>
            </div>
            <div className="h-1.5 bg-surface rounded-full overflow-hidden">
              <div
                className="h-full rounded-full transition-all duration-700"
                style={{
                  width: `${Math.round(aiProbability * 100)}%`,
                  background: aiProbability >= 0.7 ? '#ef4444' : aiProbability >= 0.3 ? '#f59e0b' : '#10b981',
                }}
              />
            </div>
          </div>
        )}

        {/* Confidence bar */}
        {confidence != null && (
          <div className="w-52">
            <div className="flex justify-between text-xs text-slate-400 mb-1">
              <span>Analysis Confidence</span>
              <span className="font-mono text-slate-300">{Math.round(confidence * 100)}%</span>
            </div>
            <div className="h-1.5 bg-surface rounded-full overflow-hidden">
              <div
                className="h-full rounded-full transition-all duration-700 bg-primary-500"
                style={{ width: `${Math.round(confidence * 100)}%` }}
              />
            </div>
          </div>
        )}
      </div>

      {/* Disclaimer */}
      <p className="text-center text-slate-500 text-xs max-w-xs leading-relaxed">
        Decision-support tool, not an absolute truth oracle.
      </p>
    </div>
  );
}
