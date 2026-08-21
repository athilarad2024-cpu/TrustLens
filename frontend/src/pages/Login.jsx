// pages/Login.jsx
import { useState, useEffect } from 'react';
import { useNavigate, useLocation, Link } from 'react-router-dom';
import { ShieldCheck, Eye, EyeOff, Mail, Lock, LogIn, AlertCircle, Loader2 } from 'lucide-react';
import { useAuth } from '../context/AuthContext';
import { loginUser } from '../services/api';

function BgOrbs() {
  return (
    <div className="pointer-events-none fixed inset-0 overflow-hidden -z-10" aria-hidden>
      <div
        className="absolute -top-40 -left-40 w-96 h-96 rounded-full opacity-20 blur-3xl"
        style={{ background: 'radial-gradient(circle, #6366f1 0%, transparent 70%)' }}
      />
      <div
        className="absolute top-1/2 -right-32 w-80 h-80 rounded-full opacity-15 blur-3xl animate-float"
        style={{ background: 'radial-gradient(circle, #06b6d4 0%, transparent 70%)' }}
      />
      <div
        className="absolute -bottom-20 left-1/3 w-64 h-64 rounded-full opacity-10 blur-3xl"
        style={{ background: 'radial-gradient(circle, #818cf8 0%, transparent 70%)' }}
      />
    </div>
  );
}

function InputField({ id, label, type, value, onChange, onBlur, error, icon: Icon, rightElement, autoComplete, placeholder }) {
  return (
    <div className="space-y-1.5">
      <label htmlFor={id} className="label">{label}</label>
      <div className="relative">
        <div className="absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-500 pointer-events-none">
          <Icon size={16} />
        </div>
        <input
          id={id}
          type={type}
          value={value}
          onChange={onChange}
          onBlur={onBlur}
          autoComplete={autoComplete}
          placeholder={placeholder}
          className={`input-field pl-10 pr-10 transition-all duration-200 ${
            error
              ? 'border-red-500/70 focus:ring-red-500/50 bg-red-950/10'
              : 'border-surface-border focus:border-primary-500/50'
          }`}
        />
        {rightElement && (
          <div className="absolute right-3 top-1/2 -translate-y-1/2">{rightElement}</div>
        )}
      </div>
      {error && (
        <p className="flex items-center gap-1.5 text-xs text-red-400 animate-slide-in-down" role="alert">
          <AlertCircle size={12} className="flex-shrink-0" />
          {error}
        </p>
      )}
    </div>
  );
}

export default function Login() {
  const { login, isAuthenticated } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const from = location.state?.from?.pathname || '/dashboard';

  useEffect(() => {
    if (isAuthenticated) navigate(from, { replace: true });
  }, [isAuthenticated, navigate, from]);

  const [email, setEmail]               = useState('');
  const [password, setPassword]         = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [touched, setTouched]           = useState({ email: false, password: false });
  const [serverError, setServerError]   = useState('');
  const [loading, setLoading]           = useState(false);

  const emailError = (() => {
    if (!touched.email) return '';
    if (!email.trim()) return 'Email is required.';
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) return 'Please enter a valid email address.';
    return '';
  })();

  const passwordError = (() => {
    if (!touched.password) return '';
    if (!password) return 'Password is required.';
    return '';
  })();

  const isFormValid = !emailError && !passwordError && email.trim() && password;

  function handleBlur(field) {
    setTouched(prev => ({ ...prev, [field]: true }));
  }

  async function handleSubmit(e) {
    e.preventDefault();
    setTouched({ email: true, password: true });
    if (!isFormValid) return;

    setLoading(true);
    setServerError('');
    try {
      const data = await loginUser(email.trim(), password);
      login(data.access_token, data.user);
      navigate(from, { replace: true });
    } catch (err) {
      setServerError(err?.message || 'Login failed. Please check your credentials.');
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center px-4 py-12 relative">
      <BgOrbs />

      <div className="w-full max-w-md animate-slide-up" style={{ animationFillMode: 'both' }}>
        <div className="card-glass p-8 sm:p-10 space-y-8">

          {/* Branding */}
          <div className="flex flex-col items-center gap-4 text-center">
            <div className="relative">
              <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-primary-500 to-accent flex items-center justify-center shadow-2xl shadow-primary-900/60 animate-pulse-glow">
                <ShieldCheck size={32} className="text-white" />
              </div>
              <div className="absolute inset-0 rounded-2xl border border-primary-400/30 scale-110" />
            </div>
            <div>
              <h1 className="text-2xl font-bold tracking-tight text-white">
                Trust<span className="text-primary-400">AI</span>
              </h1>
              <p className="text-slate-400 text-sm mt-1">Multimodal Digital Content Trust System</p>
            </div>
          </div>

          {/* Divider */}
          <div className="relative">
            <div className="absolute inset-0 flex items-center">
              <div className="w-full border-t border-surface-border" />
            </div>
            <div className="relative flex justify-center">
              <span className="bg-transparent px-3 text-xs text-slate-500 uppercase tracking-widest">
                Sign in to continue
              </span>
            </div>
          </div>

          {/* Form */}
          <form onSubmit={handleSubmit} noValidate className="space-y-5">
            {serverError && (
              <div
                className="flex items-start gap-3 rounded-xl border border-red-500/30 bg-red-950/40 px-4 py-3 animate-slide-in-down"
                role="alert"
              >
                <AlertCircle size={16} className="text-red-400 flex-shrink-0 mt-0.5" />
                <p className="text-red-300 text-sm leading-relaxed">{serverError}</p>
              </div>
            )}

            <InputField
              id="login-email"
              label="Email Address"
              type="email"
              value={email}
              onChange={e => { setEmail(e.target.value); setServerError(''); }}
              onBlur={() => handleBlur('email')}
              error={emailError}
              icon={Mail}
              autoComplete="email"
              placeholder="you@example.com"
            />

            <InputField
              id="login-password"
              label="Password"
              type={showPassword ? 'text' : 'password'}
              value={password}
              onChange={e => { setPassword(e.target.value); setServerError(''); }}
              onBlur={() => handleBlur('password')}
              error={passwordError}
              icon={Lock}
              autoComplete="current-password"
              placeholder="••••••••"
              rightElement={
                <button
                  type="button"
                  id="toggle-password-visibility"
                  onClick={() => setShowPassword(v => !v)}
                  className="text-slate-500 hover:text-slate-300 transition-colors p-0.5 rounded"
                  aria-label={showPassword ? 'Hide password' : 'Show password'}
                >
                  {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
                </button>
              }
            />

            <div className="flex justify-end">
              <Link
                to="/forgot-password"
                id="forgot-password-link"
                className="text-xs text-primary-400 hover:text-primary-300 transition-colors underline-offset-2 hover:underline"
              >
                Forgot password?
              </Link>
            </div>

            <button
              id="login-submit-btn"
              type="submit"
              disabled={loading}
              className="btn-primary w-full justify-center py-3.5 text-base mt-2"
            >
              {loading ? (
                <><Loader2 size={18} className="animate-spin" /> Signing in…</>
              ) : (
                <><LogIn size={18} /> Sign In</>
              )}
            </button>
          </form>

          {/* Sign-up link */}
          <p className="text-center text-sm text-slate-500">
            Don't have an account?{' '}
            <Link
              to="/register"
              id="signup-link"
              className="text-primary-400 hover:text-primary-300 font-medium transition-colors hover:underline underline-offset-2"
            >
              Create account
            </Link>
          </p>
        </div>
      </div>
    </div>
  );
}
