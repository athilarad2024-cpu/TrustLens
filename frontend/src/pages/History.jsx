// pages/History.jsx — enhanced with stats bar, clickable rows, and pagination
import { useEffect, useState, useCallback } from 'react';
import { useNavigate } from 'react-router-dom';
import { Clock, Image, Video, Link2, RefreshCw, TrendingUp, AlertTriangle, ShieldCheck, ChevronLeft, ChevronRight } from 'lucide-react';
import { getHistory, getAnalysis } from '../services/api';
import { useToast } from '../context/ToastContext';

const TYPE_ICON  = { url: Link2, image: Image, video: Video };
const TYPE_COLOR = { url: 'text-emerald-400', image: 'text-violet-400', video: 'text-sky-400' };
const TYPE_BG    = { url: 'bg-emerald-900/30', image: 'bg-violet-900/30', video: 'bg-sky-900/30' };

const RISK_BADGE = {
  'low':          'badge-low',
  'moderate-low': 'badge-mod-low',
  'medium':       'badge-medium',
  'high':         'badge-high',
  'very-high':    'badge-very-high',
};

const PAGE_SIZE = 10;

function MiniScoreBar({ score }) {
  const color =
    score >= 80 ? 'bg-emerald-500' :
    score >= 60 ? 'bg-teal-500' :
    score >= 40 ? 'bg-amber-500' :
    score >= 20 ? 'bg-orange-500' :
                  'bg-red-500';
  return (
    <div className="flex items-center gap-2 w-24 flex-shrink-0">
      <div className="flex-1 h-1.5 bg-surface rounded-full overflow-hidden">
        <div className={`h-full ${color} rounded-full transition-all duration-500`} style={{ width: `${score ?? 0}%` }} />
      </div>
      <span className="text-slate-200 text-xs font-bold tabular-nums w-6 text-right">{score ?? '—'}</span>
    </div>
  );
}

function HistoryRow({ item, onClick }) {
  const Icon  = TYPE_ICON[item.type] || Link2;
  const color = TYPE_COLOR[item.type] || 'text-slate-400';
  const bg    = TYPE_BG[item.type] || 'bg-slate-900/30';
  const badge = (RISK_BADGE[item.risk_level] || 'badge-medium') + ' px-2 py-0.5 rounded-full text-xs font-semibold';

  return (
    <button
      onClick={onClick}
      className="w-full flex items-center gap-4 p-4 rounded-xl hover:bg-white/5 transition-all duration-200 border border-transparent hover:border-surface-border text-left group"
    >
      <div className={`w-9 h-9 rounded-xl ${bg} flex items-center justify-center flex-shrink-0`}>
        <Icon size={15} className={color} />
      </div>
      <div className="flex-1 min-w-0">
        <p className="text-slate-200 text-sm font-medium truncate group-hover:text-white transition-colors">
          {item.type === 'url' ? item.url : `${item.type} analysis · ${item.analysis_id?.slice(0, 8)}`}
        </p>
        <p className="text-slate-500 text-xs mt-0.5">
          {item.created_at ? new Date(item.created_at).toLocaleString() : ''}
          <span className="mx-2 text-slate-600">·</span>
          <span className="capitalize">{item.type}</span>
        </p>
      </div>
      <div className="flex items-center gap-3 flex-shrink-0">
        <MiniScoreBar score={item.trust_score} />
        <span className={badge}>{item.risk_level?.replace(/-/g, ' ')}</span>
      </div>
    </button>
  );
}

function StatsBar({ results }) {
  if (!results?.length) return null;
  const total   = results.length;
  const avg     = Math.round(results.map(r => r.trust_score || 0).reduce((a, b) => a + b, 0) / total);
  const threats = results.filter(r => ['high', 'very-high'].includes(r.risk_level)).length;
  const safe    = results.filter(r => r.risk_level === 'low').length;

  return (
    <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
      {[
        { label: 'Total Analyses',   value: total,   icon: Clock,         color: 'text-primary-400' },
        { label: 'Avg Trust Score',  value: `${avg}%`, icon: TrendingUp,  color: 'text-emerald-400' },
        { label: 'Threats Found',    value: threats,  icon: AlertTriangle, color: 'text-red-400' },
        { label: 'Safe Results',     value: safe,     icon: ShieldCheck,   color: 'text-teal-400' },
      ].map(({ label, value, icon: Icon, color }) => (
        <div key={label} className="card p-4 flex items-center gap-3">
          <Icon size={18} className={color} />
          <div>
            <p className="text-lg font-bold text-white">{value}</p>
            <p className="text-slate-500 text-xs">{label}</p>
          </div>
        </div>
      ))}
    </div>
  );
}

export default function History() {
  const [data, setData]       = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError]     = useState('');
  const [filter, setFilter]   = useState('');
  const [page, setPage]       = useState(1);
  const navigate = useNavigate();
  const toast    = useToast();

  const load = useCallback(async () => {
    setLoading(true);
    setError('');
    setPage(1);
    try {
      const res = await getHistory({ type: filter || undefined, limit: 200 });
      setData(res);
    } catch (err) {
      setError(err.message || 'Failed to load history.');
    } finally {
      setLoading(false);
    }
  }, [filter]);

  useEffect(() => { load(); }, [load]);

  const handleRowClick = useCallback(async (item) => {
    if (item.type === 'url' && item.url) {
      // URL results have all data from history; navigate with it directly
      try {
        const full = await getAnalysis(item.analysis_id);
        navigate('/results', { state: { result: full } });
      } catch {
        toast.error('Could not load result', 'Try again.');
      }
    } else {
      try {
        const full = await getAnalysis(item.analysis_id);
        navigate('/results', { state: { result: full } });
      } catch {
        toast.error('Could not load result', 'Full result data may not be available for this entry.');
      }
    }
  }, [navigate, toast]);

  // Pagination
  const allResults = data?.results || [];
  const totalPages = Math.ceil(allResults.length / PAGE_SIZE);
  const pageResults = allResults.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE);

  return (
    <main className="max-w-4xl mx-auto px-4 sm:px-6 py-14 space-y-8 animate-fade-in">
      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-4">
        <div>
          <h1 className="text-3xl font-bold text-white flex items-center gap-2">
            <Clock size={24} className="text-primary-400" /> Analysis History
          </h1>
          <p className="text-slate-400 text-sm mt-1">Past analyses stored in the local database.</p>
        </div>
        <button onClick={load} className="btn-secondary">
          <RefreshCw size={14} className={loading ? 'animate-spin' : ''} /> Refresh
        </button>
      </div>

      {/* Stats */}
      {!loading && !error && allResults.length > 0 && <StatsBar results={allResults} />}

      {/* Filter tabs */}
      <div className="flex gap-2 flex-wrap">
        {['', 'url', 'image', 'video'].map(t => (
          <button
            key={t}
            onClick={() => setFilter(t)}
            className={`px-4 py-1.5 rounded-full text-sm font-medium transition-all ${
              filter === t
                ? 'bg-primary-600 text-white shadow-lg shadow-primary-900/30'
                : 'text-slate-400 hover:text-slate-200 bg-surface-card border border-surface-border hover:border-primary-700'
            }`}
          >
            {t === '' ? 'All' : t.charAt(0).toUpperCase() + t.slice(1)}
          </button>
        ))}
      </div>

      {/* Content */}
      <div className="card-glass p-2">
        {loading && (
          <div className="space-y-2 p-2">
            {[...Array(5)].map((_, i) => (
              <div key={i} className="h-16 rounded-xl shimmer" />
            ))}
          </div>
        )}
        {error && (
          <div className="text-center py-10 text-red-400 text-sm">{error}</div>
        )}
        {!loading && !error && allResults.length === 0 && (
          <div className="text-center py-16 space-y-3">
            <Clock size={32} className="text-slate-600 mx-auto" />
            <p className="text-slate-500 text-sm">No analyses found. Run an analysis to see history here.</p>
          </div>
        )}
        {!loading && !error && pageResults.length > 0 && (
          <div className="divide-y divide-surface-border/30">
            {pageResults.map(item => (
              <HistoryRow
                key={item.analysis_id}
                item={item}
                onClick={() => handleRowClick(item)}
              />
            ))}
          </div>
        )}
      </div>

      {/* Pagination */}
      {totalPages > 1 && (
        <div className="flex items-center justify-between">
          <p className="text-slate-500 text-xs">{allResults.length} total records</p>
          <div className="flex items-center gap-2">
            <button
              onClick={() => setPage(p => Math.max(1, p - 1))}
              disabled={page === 1}
              className="btn-secondary py-2 px-3 disabled:opacity-40"
            >
              <ChevronLeft size={14} />
            </button>
            <span className="text-slate-400 text-sm px-2">
              Page {page} of {totalPages}
            </span>
            <button
              onClick={() => setPage(p => Math.min(totalPages, p + 1))}
              disabled={page === totalPages}
              className="btn-secondary py-2 px-3 disabled:opacity-40"
            >
              <ChevronRight size={14} />
            </button>
          </div>
        </div>
      )}
    </main>
  );
}
