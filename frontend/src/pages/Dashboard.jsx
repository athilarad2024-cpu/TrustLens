// pages/Dashboard.jsx — Real-time stats & system overview
import { useEffect, useState, useCallback } from 'react';
import { Link } from 'react-router-dom';
import {
  Activity, ShieldCheck, AlertTriangle, TrendingUp, TrendingDown,
  Image, Video, Link2, Clock, Cpu, Database, Wifi, WifiOff,
  ArrowRight, RefreshCw, BarChart2, CheckCircle, XCircle
} from 'lucide-react';
import { getHistory, getHealth } from '../services/api';

// ── Mini donut chart ───────────────────────────────────────────────────────
function DonutChart({ data, size = 120 }) {
  const total = data.reduce((a, b) => a + b.value, 0);
  if (total === 0) return <div className="w-32 h-32 rounded-full bg-surface-card border border-surface-border flex items-center justify-center text-slate-500 text-xs">No data</div>;

  const r = 42; const cx = 60; const cy = 60;
  const circ = 2 * Math.PI * r;
  let offset = 0;
  const segments = data.map(d => {
    const pct = d.value / total;
    const seg = { ...d, offset, pct, dash: pct * circ };
    offset += pct * circ;
    return seg;
  });

  return (
    <div className="relative inline-flex items-center justify-center">
      <svg width={size} height={size} viewBox="0 0 120 120" className="rotate-[-90deg]">
        <circle cx={cx} cy={cy} r={r} fill="none" stroke="#1e293b" strokeWidth="14" />
        {segments.map((seg, i) => (
          <circle
            key={i}
            cx={cx} cy={cy} r={r}
            fill="none"
            stroke={seg.color}
            strokeWidth="14"
            strokeDasharray={`${seg.dash} ${circ - seg.dash}`}
            strokeDashoffset={-seg.offset}
            strokeLinecap="round"
            className="transition-all duration-700"
          />
        ))}
      </svg>
      <div className="absolute text-center">
        <div className="text-xl font-bold text-white">{total}</div>
        <div className="text-slate-500 text-xs">total</div>
      </div>
    </div>
  );
}

// ── Recent activity item ───────────────────────────────────────────────────
function ActivityItem({ item }) {
  const Icon  = { url: Link2, image: Image, video: Video }[item.type] || Link2;
  const color = { url: 'text-emerald-400', image: 'text-violet-400', video: 'text-sky-400' }[item.type] || 'text-slate-400';
  const bg    = { url: 'bg-emerald-900/30', image: 'bg-violet-900/30', video: 'bg-sky-900/30' }[item.type] || 'bg-slate-900/30';
  const scoreColor =
    (item.trust_score ?? 50) >= 80 ? 'text-emerald-400' :
    (item.trust_score ?? 50) >= 60 ? 'text-teal-400' :
    (item.trust_score ?? 50) >= 40 ? 'text-amber-400' : 'text-red-400';

  return (
    <div className="flex items-center gap-3 py-3 border-b border-surface-border/40 last:border-0">
      <div className={`w-8 h-8 rounded-lg ${bg} flex items-center justify-center flex-shrink-0`}>
        <Icon size={14} className={color} />
      </div>
      <div className="flex-1 min-w-0">
        <p className="text-slate-200 text-sm truncate">
          {item.type === 'url' ? item.url : `${item.type} analysis`}
        </p>
        <p className="text-slate-500 text-xs">
          {item.created_at ? new Date(item.created_at).toLocaleString() : ''}
        </p>
      </div>
      <span className={`text-sm font-bold tabular-nums flex-shrink-0 ${scoreColor}`}>
        {item.trust_score ?? '—'}
      </span>
    </div>
  );
}

// ── Model status card ──────────────────────────────────────────────────────
function ModelCard({ name, status, icon: Icon, color }) {
  const loaded = status === 'loaded';
  return (
    <div className={`card p-4 flex items-center gap-3 border ${loaded ? 'border-emerald-700/30' : 'border-amber-700/20'}`}>
      <div className={`w-9 h-9 rounded-xl flex items-center justify-center ${loaded ? 'bg-emerald-900/40' : 'bg-amber-900/20'}`}>
        <Icon size={16} className={color} />
      </div>
      <div className="flex-1 min-w-0">
        <p className="text-slate-200 text-sm font-medium truncate">{name}</p>
        <p className={`text-xs ${loaded ? 'text-emerald-400' : 'text-amber-400'}`}>
          {loaded ? '● Loaded' : '○ Not trained'}
        </p>
      </div>
      {loaded
        ? <CheckCircle size={16} className="text-emerald-400 flex-shrink-0" />
        : <XCircle    size={16} className="text-amber-400  flex-shrink-0" />
      }
    </div>
  );
}

export default function Dashboard() {
  const [data, setData]       = useState(null);
  const [health, setHealth]   = useState(null);
  const [loading, setLoading] = useState(true);
  const [lastUpdated, setLastUpdated] = useState(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [histRes, healthRes] = await Promise.all([
        getHistory({ limit: 200 }),
        getHealth(),
      ]);
      setData(histRes);
      setHealth(healthRes);
      setLastUpdated(new Date());
    } catch (e) {
      // partial data OK
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const results  = data?.results || [];
  const total    = data?.total || 0;
  const avgScore = results.length
    ? Math.round(results.map(r => r.trust_score || 0).reduce((a, b) => a + b, 0) / results.length)
    : 0;
  const threats  = results.filter(r => ['high', 'very-high'].includes(r.risk_level)).length;
  const safe     = results.filter(r => r.risk_level === 'low').length;
  const byType   = {
    url:   results.filter(r => r.type === 'url').length,
    image: results.filter(r => r.type === 'image').length,
    video: results.filter(r => r.type === 'video').length,
  };
  const riskDist = [
    { label: 'Low',       value: results.filter(r => r.risk_level === 'low').length,       color: '#10b981' },
    { label: 'Moderate',  value: results.filter(r => ['moderate-low','medium'].includes(r.risk_level)).length, color: '#f59e0b' },
    { label: 'High',      value: results.filter(r => ['high','very-high'].includes(r.risk_level)).length,      color: '#ef4444' },
  ];

  const typeDist = [
    { label: 'URL',   value: byType.url,   color: '#10b981' },
    { label: 'Image', value: byType.image, color: '#8b5cf6' },
    { label: 'Video', value: byType.video, color: '#0ea5e9' },
  ];

  const Skeleton = () => <div className="h-6 w-20 rounded shimmer" />;

  return (
    <main className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12 space-y-8 animate-fade-in">

      {/* Header */}
      <div className="flex items-center justify-between flex-wrap gap-4">
        <div>
          <h1 className="text-3xl font-bold text-white flex items-center gap-2">
            <Activity size={26} className="text-primary-400" /> Dashboard
          </h1>
          <p className="text-slate-400 text-sm mt-1">
            {lastUpdated ? `Last updated: ${lastUpdated.toLocaleTimeString()}` : 'Loading…'}
          </p>
        </div>
        <button onClick={load} className="btn-secondary">
          <RefreshCw size={14} className={loading ? 'animate-spin' : ''} /> Refresh
        </button>
      </div>

      {/* ── KPI cards ─────────────────────────────── */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {[
          { label: 'Total Analyses', value: loading ? null : total,    icon: BarChart2,     color: 'from-primary-600 to-primary-700', text: 'text-primary-300' },
          { label: 'Avg Trust Score', value: loading ? null : `${avgScore}%`, icon: TrendingUp, color: 'from-emerald-600 to-teal-600', text: 'text-emerald-300' },
          { label: 'Threats Detected', value: loading ? null : threats, icon: AlertTriangle, color: 'from-red-600 to-orange-600',     text: 'text-red-300' },
          { label: 'Safe Results',    value: loading ? null : safe,    icon: ShieldCheck,   color: 'from-teal-600 to-cyan-600',      text: 'text-teal-300' },
        ].map(({ label, value, icon: Icon, color, text }) => (
          <div key={label} className="stat-card">
            <div className={`w-10 h-10 rounded-xl bg-gradient-to-br ${color} flex items-center justify-center shadow-lg`}>
              <Icon size={18} className="text-white" />
            </div>
            <div>
              {value != null
                ? <p className={`text-3xl font-extrabold ${text}`}>{value}</p>
                : <Skeleton />
              }
              <p className="text-slate-500 text-xs mt-0.5">{label}</p>
            </div>
          </div>
        ))}
      </div>

      {/* ── Charts row ────────────────────────────── */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        {/* Risk Distribution */}
        <div className="card-glass p-6 space-y-4">
          <h2 className="text-lg font-semibold text-slate-100 flex items-center gap-2">
            <BarChart2 size={18} className="text-primary-400" /> Risk Distribution
          </h2>
          <div className="flex items-center gap-8">
            {loading
              ? <div className="w-32 h-32 rounded-full shimmer" />
              : <DonutChart data={riskDist} />
            }
            <div className="space-y-3 flex-1">
              {riskDist.map(({ label, value, color }) => (
                <div key={label} className="flex items-center gap-2">
                  <div className="w-2.5 h-2.5 rounded-full flex-shrink-0" style={{ background: color }} />
                  <span className="text-slate-400 text-sm flex-1">{label}</span>
                  <span className="text-slate-200 text-sm font-semibold tabular-nums">
                    {loading ? '—' : value}
                  </span>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Analysis Type Distribution */}
        <div className="card-glass p-6 space-y-4">
          <h2 className="text-lg font-semibold text-slate-100 flex items-center gap-2">
            <Activity size={18} className="text-primary-400" /> Analysis Types
          </h2>
          <div className="flex items-center gap-8">
            {loading
              ? <div className="w-32 h-32 rounded-full shimmer" />
              : <DonutChart data={typeDist} />
            }
            <div className="space-y-3 flex-1">
              {[
                { label: 'URL',   value: byType.url,   color: '#10b981', icon: Link2  },
                { label: 'Image', value: byType.image, color: '#8b5cf6', icon: Image  },
                { label: 'Video', value: byType.video, color: '#0ea5e9', icon: Video  },
              ].map(({ label, value, color, icon: Icon }) => (
                <div key={label} className="flex items-center gap-2">
                  <Icon size={13} style={{ color }} className="flex-shrink-0" />
                  <span className="text-slate-400 text-sm flex-1">{label}</span>
                  <span className="text-slate-200 text-sm font-semibold tabular-nums">
                    {loading ? '—' : value}
                  </span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* ── Bottom row ────────────────────────────── */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">

        {/* Recent Activity */}
        <div className="lg:col-span-2 card-glass p-6 space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-lg font-semibold text-slate-100 flex items-center gap-2">
              <Clock size={18} className="text-primary-400" /> Recent Activity
            </h2>
            <Link to="/history" className="text-primary-400 text-sm hover:text-primary-300 flex items-center gap-1 transition-colors">
              View all <ArrowRight size={13} />
            </Link>
          </div>
          <div>
            {loading && [...Array(5)].map((_, i) => (
              <div key={i} className="py-3 border-b border-surface-border/40 last:border-0">
                <div className="h-4 rounded shimmer mb-1.5" />
                <div className="h-3 w-32 rounded shimmer" />
              </div>
            ))}
            {!loading && results.slice(0, 6).map(item => (
              <ActivityItem key={item.analysis_id} item={item} />
            ))}
            {!loading && results.length === 0 && (
              <p className="text-slate-500 text-sm py-6 text-center">No analyses yet. Run one to see activity here.</p>
            )}
          </div>
        </div>

        {/* System Health */}
        <div className="card-glass p-6 space-y-4">
          <h2 className="text-lg font-semibold text-slate-100 flex items-center gap-2">
            <Cpu size={18} className="text-primary-400" /> System Health
          </h2>
          <div className="space-y-3">
            {/* Backend status */}
            <div className={`card p-3 flex items-center gap-3 border ${health ? 'border-emerald-700/30' : 'border-red-700/30'}`}>
              {health ? <Wifi size={15} className="text-emerald-400" /> : <WifiOff size={15} className="text-red-400" />}
              <div className="flex-1">
                <p className="text-slate-200 text-sm font-medium">Backend API</p>
                <p className={`text-xs ${health ? 'text-emerald-400' : 'text-red-400'}`}>
                  {loading ? 'Checking…' : health ? '● Online' : '○ Offline'}
                </p>
              </div>
            </div>

            {/* Model statuses */}
            {health?.models && (
              <>
                <ModelCard
                  name="URL Phishing Model"
                  status={health.models.url_phishing}
                  icon={Link2}
                  color="text-emerald-400"
                />
                <ModelCard
                  name="Image AI Detector"
                  status={health.models.image_detection}
                  icon={Image}
                  color="text-violet-400"
                />
                <ModelCard
                  name="Video Deepfake Model"
                  status={health.models.video_deepfake}
                  icon={Video}
                  color="text-sky-400"
                />
              </>
            )}

            {/* Database status */}
            {health?.database && (
              <div className={`card p-3 flex items-center gap-3 border ${health.database === 'connected' ? 'border-emerald-700/30' : 'border-red-700/30'}`}>
                <Database size={15} className={health.database === 'connected' ? 'text-emerald-400' : 'text-red-400'} />
                <div>
                  <p className="text-slate-200 text-sm font-medium">Database</p>
                  <p className={`text-xs ${health.database === 'connected' ? 'text-emerald-400' : 'text-red-400'}`}>
                    {health.database === 'connected' ? '● Connected' : '○ Unavailable'}
                  </p>
                </div>
              </div>
            )}
          </div>

          {/* Quick actions */}
          <div className="pt-2 space-y-2">
            <p className="text-slate-500 text-xs uppercase tracking-wide font-medium">Quick Analyze</p>
            <div className="grid grid-cols-3 gap-2">
              {[
                { to: '/analyze/url',   icon: Link2,  label: 'URL',   color: 'hover:text-emerald-300' },
                { to: '/analyze/image', icon: Image,  label: 'Image', color: 'hover:text-violet-300' },
                { to: '/analyze/video', icon: Video,  label: 'Video', color: 'hover:text-sky-300' },
              ].map(({ to, icon: Icon, label, color }) => (
                <Link
                  key={to}
                  to={to}
                  className={`card p-3 flex flex-col items-center gap-1 hover:border-surface-muted transition-all duration-200 ${color}`}
                >
                  <Icon size={16} className="text-slate-400" />
                  <span className="text-slate-500 text-xs">{label}</span>
                </Link>
              ))}
            </div>
          </div>
        </div>
      </div>
    </main>
  );
}
