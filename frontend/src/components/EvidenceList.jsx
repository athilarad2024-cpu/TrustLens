// components/EvidenceList.jsx
import { AlertTriangle, Info, AlertCircle, CheckCircle } from 'lucide-react';

const SEV_CONFIG = {
  high:   { dot: 'dot-high',   icon: AlertTriangle, color: 'text-red-400',    bg: 'bg-red-900/20 border-red-800/40' },
  medium: { dot: 'dot-medium', icon: AlertCircle,   color: 'text-amber-400',  bg: 'bg-amber-900/20 border-amber-800/40' },
  low:    { dot: 'dot-low',    icon: CheckCircle,   color: 'text-teal-400',   bg: 'bg-teal-900/20 border-teal-800/40' },
  info:   { dot: 'dot-info',   icon: Info,          color: 'text-slate-400',  bg: 'bg-slate-800/30 border-slate-700/40' },
};

function EvidenceItem({ item, index }) {
  const sev = SEV_CONFIG[item.severity] || SEV_CONFIG.info;
  const Icon = sev.icon;

  return (
    <div
      className={`flex gap-3 p-4 rounded-xl border ${sev.bg} animate-slide-up`}
      style={{ animationDelay: `${index * 60}ms`, animationFillMode: 'both' }}
    >
      <Icon size={16} className={`${sev.color} flex-shrink-0 mt-0.5`} />
      <div className="flex-1 min-w-0">
        <p className="text-slate-200 text-sm leading-relaxed">{item.description}</p>
        <div className="flex flex-wrap gap-2 mt-1.5">
          <span className="text-xs text-slate-500 font-mono bg-surface px-2 py-0.5 rounded">
            {item.source}
          </span>
          {item.supporting_value && (
            <span className="text-xs text-slate-500 font-mono bg-surface px-2 py-0.5 rounded">
              {item.supporting_value}
            </span>
          )}
        </div>
      </div>
    </div>
  );
}

export default function EvidenceList({ evidence = [] }) {
  if (!evidence.length) {
    return (
      <div className="text-center py-8 text-slate-500 text-sm">
        No evidence items available for this analysis.
      </div>
    );
  }

  // Sort: high → medium → low → info
  const order = { high: 0, medium: 1, low: 2, info: 3 };
  const sorted = [...evidence].sort((a, b) => (order[a.severity] ?? 3) - (order[b.severity] ?? 3));

  return (
    <div className="space-y-3">
      {sorted.map((item, i) => (
        <EvidenceItem key={i} item={item} index={i} />
      ))}
    </div>
  );
}
