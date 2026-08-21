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
  };
  return (map[risk] || 'badge-medium') + ' px-3 py-1 rounded-full text-xs font-semibold';
}

export default function TrustScoreCard({ score, riskLevel, confidence, prediction }) {
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

      {/* Risk badge */}
      <div className="text-center space-y-3">
        <span className={badgeClass(riskLevel)}>{riskLabel(riskLevel)}</span>

        {prediction && (
          <p className="text-slate-300 text-sm font-medium capitalize">
            {prediction.replace(/_/g, ' ')}
          </p>
        )}

        {confidence != null && (
          <div className="w-48">
            <div className="flex justify-between text-xs text-slate-500 mb-1">
              <span>Confidence</span>
              <span>{Math.round(confidence * 100)}%</span>
            </div>
            <div className="h-1.5 bg-surface rounded-full overflow-hidden">
              <div
                className="h-full rounded-full transition-all duration-700"
                style={{ width: `${Math.round(confidence * 100)}%`, background: colors.stroke }}
              />
            </div>
          </div>
        )}
      </div>

      {/* Disclaimer */}
      <p className="text-center text-slate-500 text-xs max-w-xs leading-relaxed">
        Trust Score is a probabilistic risk estimate, not a guarantee of authenticity.
      </p>
    </div>
  );
}
