// context/ToastContext.jsx
// Global toast notification system — wrap App with <ToastProvider>
import { createContext, useCallback, useContext, useEffect, useRef, useState } from 'react';
import { CheckCircle2, XCircle, Info, AlertTriangle, X } from 'lucide-react';

const ToastContext = createContext(null);

let _uid = 0;
const uid = () => ++_uid;

const ICONS = {
  success: CheckCircle2,
  error:   XCircle,
  info:    Info,
  warning: AlertTriangle,
};

const COLORS = {
  success: {
    border: 'border-emerald-500/40',
    icon:   'text-emerald-400',
    bar:    'bg-emerald-500',
    bg:     'bg-emerald-950/60',
  },
  error: {
    border: 'border-red-500/40',
    icon:   'text-red-400',
    bar:    'bg-red-500',
    bg:     'bg-red-950/60',
  },
  info: {
    border: 'border-primary-500/40',
    icon:   'text-primary-400',
    bar:    'bg-primary-500',
    bg:     'bg-primary-950/60',
  },
  warning: {
    border: 'border-amber-500/40',
    icon:   'text-amber-400',
    bar:    'bg-amber-500',
    bg:     'bg-amber-950/60',
  },
};

function Toast({ id, type = 'info', title, message, duration = 4000, onDismiss }) {
  const [visible, setVisible] = useState(false);
  const [progress, setProgress] = useState(100);
  const intervalRef = useRef(null);
  const colors = COLORS[type] || COLORS.info;
  const Icon = ICONS[type] || Info;

  useEffect(() => {
    // mount → slide in
    const t = setTimeout(() => setVisible(true), 10);
    // progress bar countdown
    const step = 50;
    intervalRef.current = setInterval(() => {
      setProgress(p => {
        const next = p - (step / duration) * 100;
        if (next <= 0) {
          clearInterval(intervalRef.current);
          handleDismiss();
          return 0;
        }
        return next;
      });
    }, step);
    return () => { clearTimeout(t); clearInterval(intervalRef.current); };
  }, [duration]);

  const handleDismiss = useCallback(() => {
    setVisible(false);
    setTimeout(() => onDismiss(id), 300);
  }, [id, onDismiss]);

  return (
    <div
      className={`
        relative overflow-hidden rounded-2xl border backdrop-blur-xl shadow-2xl
        ${colors.border} ${colors.bg}
        transition-all duration-300 ease-out
        ${visible ? 'opacity-100 translate-x-0' : 'opacity-0 translate-x-8'}
        w-80 max-w-[90vw]
      `}
    >
      <div className="flex items-start gap-3 px-4 py-3.5">
        <Icon size={18} className={`${colors.icon} flex-shrink-0 mt-0.5`} />
        <div className="flex-1 min-w-0">
          {title && <p className="text-slate-100 text-sm font-semibold leading-tight">{title}</p>}
          {message && <p className="text-slate-400 text-xs mt-0.5 leading-relaxed">{message}</p>}
        </div>
        <button
          onClick={handleDismiss}
          className="text-slate-500 hover:text-slate-300 transition-colors flex-shrink-0 mt-0.5"
        >
          <X size={14} />
        </button>
      </div>
      {/* Progress bar */}
      <div className="h-0.5 w-full bg-white/5">
        <div
          className={`h-full ${colors.bar} transition-none`}
          style={{ width: `${progress}%` }}
        />
      </div>
    </div>
  );
}

export function ToastProvider({ children }) {
  const [toasts, setToasts] = useState([]);

  const addToast = useCallback((opts) => {
    const id = uid();
    setToasts(prev => [...prev, { id, ...opts }]);
    return id;
  }, []);

  const removeToast = useCallback((id) => {
    setToasts(prev => prev.filter(t => t.id !== id));
  }, []);

  const toast = {
    success: (title, message, opts) => addToast({ type: 'success', title, message, ...opts }),
    error:   (title, message, opts) => addToast({ type: 'error',   title, message, ...opts }),
    info:    (title, message, opts) => addToast({ type: 'info',    title, message, ...opts }),
    warning: (title, message, opts) => addToast({ type: 'warning', title, message, ...opts }),
  };

  return (
    <ToastContext.Provider value={toast}>
      {children}
      {/* Toast container — top-right */}
      <div className="fixed top-20 right-4 z-[9999] flex flex-col gap-3 pointer-events-none">
        {toasts.map(t => (
          <div key={t.id} className="pointer-events-auto">
            <Toast {...t} onDismiss={removeToast} />
          </div>
        ))}
      </div>
    </ToastContext.Provider>
  );
}

export function useToast() {
  const ctx = useContext(ToastContext);
  if (!ctx) throw new Error('useToast must be used inside <ToastProvider>');
  return ctx;
}
