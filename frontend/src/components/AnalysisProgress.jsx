// components/AnalysisProgress.jsx — spinner shown while analysis runs
import { Loader2 } from 'lucide-react';

export default function AnalysisProgress({ label = 'Analyzing…', progress }) {
  return (
    <div className="card-glass p-12 flex flex-col items-center gap-6 animate-fade-in">
      <div className="relative">
        <div className="w-20 h-20 rounded-full border-2 border-primary-900" />
        <div className="absolute inset-0 w-20 h-20 rounded-full border-2 border-transparent
                        border-t-primary-500 animate-spin" />
        <div className="absolute inset-3 w-14 h-14 rounded-full border-2 border-transparent
                        border-t-accent animate-spin-slow" />
      </div>
      <div className="text-center">
        <p className="text-slate-200 font-semibold">{label}</p>
        <p className="text-slate-500 text-sm mt-1">This may take a moment for video files.</p>
      </div>
      {progress != null && (
        <div className="w-48">
          <div className="h-1.5 bg-surface rounded-full overflow-hidden">
            <div
              className="h-full bg-gradient-to-r from-primary-500 to-accent rounded-full transition-all duration-300"
              style={{ width: `${Math.round(progress)}%` }}
            />
          </div>
          <p className="text-center text-slate-500 text-xs mt-1">{Math.round(progress)}% uploaded</p>
        </div>
      )}
    </div>
  );
}
