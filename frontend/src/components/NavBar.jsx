// components/NavBar.jsx
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { ShieldCheck, Image, Video, Link2, Clock, Info, LayoutDashboard, Menu, X, Sun, Moon, Wifi, WifiOff, LogOut } from 'lucide-react';
import { useState, useEffect, useCallback } from 'react';
import { getHealth } from '../services/api';
import { useAuth } from '../context/AuthContext';

const links = [
  { to: '/',              label: 'Home',      icon: ShieldCheck },
  { to: '/dashboard',     label: 'Dashboard', icon: LayoutDashboard },
  { to: '/analyze/image', label: 'Image',     icon: Image },
  { to: '/analyze/video', label: 'Video',     icon: Video },
  { to: '/analyze/url',   label: 'URL',       icon: Link2 },
  { to: '/history',       label: 'History',   icon: Clock },
  { to: '/about',         label: 'About',     icon: Info },
];

function HealthDot({ status }) {
  const colors = {
    online:  { dot: 'bg-emerald-400', ring: 'bg-emerald-400/30', label: 'All systems online',  icon: Wifi },
    partial: { dot: 'bg-amber-400',   ring: 'bg-amber-400/30',   label: 'Some models offline', icon: Wifi },
    offline: { dot: 'bg-red-400',     ring: 'bg-red-400/30',     label: 'Backend offline',     icon: WifiOff },
  };
  const c = colors[status] || colors.offline;

  return (
    <div className="relative group">
      <div className="flex items-center gap-1.5 cursor-default">
        <span className={`relative flex h-2.5 w-2.5`}>
          <span className={`animate-ping absolute inline-flex h-full w-full rounded-full ${c.ring} opacity-75`}></span>
          <span className={`relative inline-flex rounded-full h-2.5 w-2.5 ${c.dot}`}></span>
        </span>
        <span className="text-xs text-slate-500 hidden lg:block">API</span>
      </div>
      {/* Tooltip */}
      <div className="absolute right-0 top-6 hidden group-hover:block z-50 w-52">
        <div className="bg-surface-card border border-surface-border rounded-xl p-3 shadow-2xl text-xs text-slate-400">
          {c.label}
        </div>
      </div>
    </div>
  );
}

export default function NavBar() {
  const { pathname } = useLocation();
  const navigate = useNavigate();
  const { isAuthenticated, logout, user } = useAuth();
  const [menuOpen, setMenuOpen] = useState(false);
  const [lightMode, setLightMode] = useState(() => localStorage.getItem('trustai-theme') === 'light');
  const [health, setHealth] = useState('offline');

  // Sync theme to body class
  useEffect(() => {
    document.body.classList.toggle('light-mode', lightMode);
    localStorage.setItem('trustai-theme', lightMode ? 'light' : 'dark');
  }, [lightMode]);

  // Poll backend health every 30s
  const checkHealth = useCallback(async () => {
    try {
      const data = await getHealth();
      const models = Object.values(data.models || {});
      const loaded = models.filter(m => m === 'loaded').length;
      if (loaded === models.length) setHealth('online');
      else if (loaded > 0) setHealth('partial');
      else setHealth('partial');
    } catch {
      setHealth('offline');
    }
  }, []);

  useEffect(() => {
    checkHealth();
    const id = setInterval(checkHealth, 30_000);
    return () => clearInterval(id);
  }, [checkHealth]);

  // Close drawer on route change
  useEffect(() => setMenuOpen(false), [pathname]);

  return (
    <>
      <nav
        className="sticky top-0 z-50 border-b border-surface-border"
        style={{ background: 'rgba(15,23,42,0.88)', backdropFilter: 'blur(20px)' }}
      >
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex items-center justify-between h-16">
            {/* Logo */}
            <Link to="/" className="flex items-center gap-2.5 group flex-shrink-0">
              <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-primary-500 to-accent flex items-center justify-center shadow-lg shadow-primary-900/50 group-hover:scale-110 transition-transform">
                <ShieldCheck className="text-white" size={18} />
              </div>
              <span className="font-bold text-lg tracking-tight text-white">
                Trust<span className="text-primary-400">AI</span>
              </span>
            </Link>

            {/* Desktop links */}
            <div className="hidden md:flex items-center gap-0.5">
              {links.map(({ to, label, icon: Icon }) => {
                const active = pathname === to;
                return (
                  <Link
                    key={to}
                    to={to}
                    className={`flex items-center gap-1.5 px-3 py-2 rounded-lg text-sm font-medium transition-all duration-200 ${
                      active
                        ? 'bg-primary-600/30 text-primary-300'
                        : 'text-slate-400 hover:text-slate-200 hover:bg-white/5'
                    }`}
                  >
                    <Icon size={14} />
                    {label}
                  </Link>
                );
              })}
            </div>

            {/* Right controls */}
            <div className="flex items-center gap-3">
              <HealthDot status={health} />

              {/* Theme toggle */}
              <button
                onClick={() => setLightMode(m => !m)}
                className="w-8 h-8 rounded-lg flex items-center justify-center text-slate-400 hover:text-slate-200 hover:bg-white/5 transition-all"
                title={lightMode ? 'Switch to dark mode' : 'Switch to light mode'}
              >
                {lightMode ? <Moon size={16} /> : <Sun size={16} />}
              </button>

              {/* Logout button — only when authenticated */}
              {isAuthenticated && (
                <button
                  id="navbar-logout-btn"
                  onClick={() => { logout(); navigate('/login'); }}
                  className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-medium text-slate-400 hover:text-red-300 hover:bg-red-500/10 border border-transparent hover:border-red-500/20 transition-all duration-200"
                  title={`Logout${user?.name ? ` (${user.name})` : ''}`}
                >
                  <LogOut size={14} />
                  <span className="hidden sm:inline">Logout</span>
                </button>
              )}

              {/* Mobile hamburger */}
              <button
                onClick={() => setMenuOpen(o => !o)}
                className="md:hidden w-8 h-8 rounded-lg flex items-center justify-center text-slate-400 hover:text-slate-200 hover:bg-white/5 transition-all"
              >
                {menuOpen ? <X size={18} /> : <Menu size={18} />}
              </button>
            </div>
          </div>
        </div>
      </nav>

      {/* Mobile drawer overlay */}
      {menuOpen && (
        <div className="drawer-overlay md:hidden" onClick={() => setMenuOpen(false)} />
      )}

      {/* Mobile slide-out drawer */}
      <div
        className={`fixed top-16 left-0 bottom-0 w-72 z-50 md:hidden transition-transform duration-300 ease-out
          border-r border-surface-border
          ${menuOpen ? 'translate-x-0' : '-translate-x-full'}`}
        style={{ background: 'rgba(15,23,42,0.97)', backdropFilter: 'blur(20px)' }}
      >
        <div className="p-4 space-y-1">
          {links.map(({ to, label, icon: Icon }) => {
            const active = pathname === to;
            return (
              <Link
                key={to}
                to={to}
                onClick={() => setMenuOpen(false)}
                className={`flex items-center gap-3 px-4 py-3 rounded-xl text-sm font-medium transition-all duration-200 ${
                  active
                    ? 'bg-primary-600/30 text-primary-300 border border-primary-500/30'
                    : 'text-slate-400 hover:text-slate-200 hover:bg-white/5'
                }`}
              >
                <Icon size={16} />
                {label}
              </Link>
            );
          })}
        </div>
        <div className="absolute bottom-8 left-0 right-0 px-4">
          <p className="text-slate-600 text-xs text-center">TrustAI v1.0.0</p>
        </div>
      </div>
    </>
  );
}
