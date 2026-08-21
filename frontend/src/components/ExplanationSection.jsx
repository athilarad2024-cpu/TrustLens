// components/ExplanationSection.jsx
import { MessageSquare, AlertTriangle } from 'lucide-react';

export default function ExplanationSection({ explanation, limitations = [] }) {
  if (!explanation) return null;

  const reasons = explanation?.reasons || [];
  const extraLimitations = explanation?.limitations || [];
  const allLimitations = [...new Set([...limitations, ...extraLimitations])];

  return (
    <div className="space-y-6 animate-fade-in">
      {/* Prediction label */}
      {explanation.prediction_label && (
        <div className="flex items-center gap-2">
          <MessageSquare size={18} className="text-primary-400" />
          <h3 className="text-lg font-semibold text-slate-100">{explanation.prediction_label}</h3>
        </div>
      )}

      {/* Reasons */}
      {reasons.length > 0 && (
        <div>
          <p className="text-sm font-medium text-slate-400 mb-3 uppercase tracking-wide">Why this result?</p>
          <ol className="space-y-3">
            {reasons.map((reason, i) => (
              <li
                key={i}
                className="flex gap-3 animate-slide-up"
                style={{ animationDelay: `${i * 80}ms`, animationFillMode: 'both' }}
              >
                <span className="flex-shrink-0 w-6 h-6 rounded-full bg-primary-600/40 text-primary-300
                                 text-xs font-bold flex items-center justify-center mt-0.5">
                  {i + 1}
                </span>
                <p className="text-slate-300 text-sm leading-relaxed">{reason}</p>
              </li>
            ))}
          </ol>
        </div>
      )}

      {/* Limitations */}
      {allLimitations.length > 0 && (
        <div className="bg-amber-900/10 border border-amber-800/30 rounded-xl p-4">
          <div className="flex items-center gap-2 mb-3">
            <AlertTriangle size={15} className="text-amber-400" />
            <p className="text-sm font-medium text-amber-400">Limitations & Uncertainty</p>
          </div>
          <ul className="space-y-1.5">
            {allLimitations.map((lim, i) => (
              <li key={i} className="text-amber-200/70 text-xs leading-relaxed flex gap-2">
                <span className="text-amber-600 flex-shrink-0">•</span>
                {lim}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
