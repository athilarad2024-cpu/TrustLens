// pages/Register.jsx
import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import {
  ShieldCheck, User, Mail, Lock, Eye, EyeOff,
  AlertCircle, CheckCircle2, Loader2, UserPlus,
} from 'lucide-react';
import { registerUser } from '../services/api';

// ── Shared background orbs ────────────────────────────────────────────────────
function BgOrbs() {
  return (
    <div className="pointer-events-none fixed inset-0 overflow-hidden -z-10" aria-hidden>
      <div
        className="absolute -top-40 -right-40 w-96 h-96 rounded-full opacity-20 blur-3xl"
        style={{ background: 'radial-gradient(circle, #06b6d4 0%, transparent 70%)' }}
      />
      <div
        className="absolute bottom-0 -left-32 w-80 h-80 rounded-full opacity-15 blur-3xl animate-float"
        style={{ background: 'radial-gradient(circle, #6366f1 0%, transparent 70%)' }}
      />
    </div>
  );
}

// ── Input with icon + validation ──────────────────────────────────────────────
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

// ── Password strength indicator ───────────────────────────────────────────────
const STRENGTH_RULES = [
  { label: 'At least 8 characters',      test: p => p.length >= 8 },
  { label: 'One uppercase letter',        test: p => /[A-Z]/.test(p) },
  { label: 'One lowercase letter',        test: p => /[a-z]/.test(p) },
  { label: 'One number',                  test: p => /\d/.test(p) },
];

function PasswordStrength({ password }) {
  if (!password) return null;
  const passed = STRENGTH_RULES.filter(r => r.test(password)).length;
  const colors = ['bg-red-500', 'bg-orange-500', 'bg-amber-400', 'bg-emerald-500'];
  const barColor = colors[passed - 1] || 'bg-red-500';

  return (
    <div className="space-y-2 pt-1">
      {/* Bar */}
      <div className="flex gap-1">
        {STRENGTH_RULES.map((_, i) => (
          <div
            key={i}
            className={`h-1 flex-1 rounded-full transition-all duration-300 ${
              i < passed ? barColor : 'bg-surface-border'
            }`}
          />
        ))}
      </div>
      {/* Rules checklist */}
      <ul className="space-y-0.5">
        {STRENGTH_RULES.map(rule => {
          const ok = rule.test(password);
          return (
            <li key={rule.label} className={`flex items-center gap-1.5 text-xs transition-colors ${ok ? 'text-emerald-400' : 'text-slate-500'}`}>
              <CheckCircle2 size={11} className={ok ? 'text-emerald-400' : 'text-slate-600'} />
              {rule.label}
            </li>
          );
        })}
      </ul>
    </div>
  );
}

// ── Main Register component ───────────────────────────────────────────────────
export default function Register() {
  const navigate = useNavigate();

  const [fields, setFields] = useState({ name: '', email: '', password: '', confirm: '' });
  const [touched, setTouched] = useState({ name: false, email: false, password: false, confirm: false });
  const [showPassword, setShowPassword]   = useState(false);
  const [showConfirm, setShowConfirm]     = useState(false);
  const [serverError, setServerError]     = useState('');
  const [successMsg, setSuccessMsg]       = useState('');
  const [loading, setLoading]             = useState(false);

  function set(field, val) {
    setFields(prev => ({ ...prev, [field]: val }));
    setServerError('');
  }
  function blur(field) {
    setTouched(prev => ({ ...prev, [field]: true }));
  }

  // ── Inline validation ───────────────────────────────────────────────────────
  const errors = {
    name: (() => {
      if (!touched.name) return '';
      if (!fields.name.trim()) return 'Full name is required.';
      return '';
    })(),
    email: (() => {
      if (!touched.email) return '';
      if (!fields.email.trim()) return 'Email is required.';
      if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(fields.email)) return 'Please enter a valid email address.';
      return '';
    })(),
    password: (() => {
      if (!touched.password) return '';
      if (!fields.password) return 'Password is required.';
      if (fields.password.length < 8) return 'Password must be at least 8 characters.';
      if (!/[A-Z]/.test(fields.password)) return 'Password must contain an uppercase letter.';
      if (!/[a-z]/.test(fields.password)) return 'Password must contain a lowercase letter.';
      if (!/\d/.test(fields.password)) return 'Password must contain a number.';
      return '';
    })(),
    confirm: (() => {
      if (!touched.confirm) return '';
      if (!fields.confirm) return 'Please confirm your password.';
      if (fields.confirm !== fields.password) return 'Passwords do not match.';
      return '';
    })(),
  };

  const isStrong = STRENGTH_RULES.every(r => r.test(fields.password));
  const isFormValid =
    fields.name.trim() && fields.email.trim() && isStrong &&
    fields.confirm === fields.password &&
    !Object.values(errors).some(Boolean);

  // ── Submit ──────────────────────────────────────────────────────────────────
  async function handleSubmit(e) {
    e.preventDefault();
    setTouched({ name: true, email: true, password: true, confirm: true });
    if (!isFormValid) return;

    setLoading(true);
    setServerError('');
    setSuccessMsg('');

    try {
      const data = await registerUser(
        fields.name.trim(),
        fields.email.trim(),
        fields.password,
        fields.confirm,
      );
      setSuccessMsg(data.message || 'Account created! Redirecting to login…');
      setTimeout(() => navigate('/login', { state: { registered: true } }), 2000);
    } catch (err) {
      setServerError(err?.message || 'Registration failed. Please try again.');
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center px-4 py-12 relative">
      <BgOrbs />

      <div className="w-full max-w-md animate-slide-up" style={{ animationFillMode: 'both' }}>
        <div className="card-glass p-8 sm:p-10 space-y-7">

          {/* Branding */}
          <div className="flex flex-col items-center gap-3 text-center">
            <div className="relative">
              <div className="w-14 h-14 rounded-2xl bg-gradient-to-br from-primary-500 to-accent flex items-center justify-center shadow-2xl shadow-primary-900/60">
                <ShieldCheck size={28} className="text-white" />
              </div>
              <div className="absolute inset-0 rounded-2xl border border-primary-400/30 scale-110" />
            </div>
            <div>
              <h1 className="text-2xl font-bold tracking-tight text-white">
                Create your account
              </h1>
              <p className="text-slate-400 text-sm mt-1">
                Trust<span className="text-primary-400">AI</span> — Multimodal Content Trust System
              </p>
            </div>
          </div>

          {/* Form */}
          <form onSubmit={handleSubmit} noValidate className="space-y-4">

            {/* Server error */}
            {serverError && (
              <div className="flex items-start gap-3 rounded-xl border border-red-500/30 bg-red-950/40 px-4 py-3 animate-slide-in-down" role="alert">
                <AlertCircle size={16} className="text-red-400 flex-shrink-0 mt-0.5" />
                <p className="text-red-300 text-sm leading-relaxed">{serverError}</p>
              </div>
            )}

            {/* Success message */}
            {successMsg && (
              <div className="flex items-start gap-3 rounded-xl border border-emerald-500/30 bg-emerald-950/40 px-4 py-3 animate-slide-in-down" role="status">
                <CheckCircle2 size={16} className="text-emerald-400 flex-shrink-0 mt-0.5" />
                <p className="text-emerald-300 text-sm leading-relaxed">{successMsg}</p>
              </div>
            )}

            {/* Full name */}
            <InputField
              id="register-name"
              label="Full Name"
              type="text"
              value={fields.name}
              onChange={e => set('name', e.target.value)}
              onBlur={() => blur('name')}
              error={errors.name}
              icon={User}
              autoComplete="name"
              placeholder="Jane Smith"
            />

            {/* Email */}
            <InputField
              id="register-email"
              label="Email Address"
              type="email"
              value={fields.email}
              onChange={e => set('email', e.target.value)}
              onBlur={() => blur('email')}
              error={errors.email}
              icon={Mail}
              autoComplete="email"
              placeholder="you@example.com"
            />

            {/* Password */}
            <div>
              <InputField
                id="register-password"
                label="Password"
                type={showPassword ? 'text' : 'password'}
                value={fields.password}
                onChange={e => set('password', e.target.value)}
                onBlur={() => blur('password')}
                error={errors.password}
                icon={Lock}
                autoComplete="new-password"
                placeholder="••••••••"
                rightElement={
                  <button
                    type="button"
                    onClick={() => setShowPassword(v => !v)}
                    className="text-slate-500 hover:text-slate-300 transition-colors p-0.5 rounded"
                    aria-label={showPassword ? 'Hide password' : 'Show password'}
                  >
                    {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
                  </button>
                }
              />
              {touched.password && <PasswordStrength password={fields.password} />}
            </div>

            {/* Confirm password */}
            <InputField
              id="register-confirm"
              label="Confirm Password"
              type={showConfirm ? 'text' : 'password'}
              value={fields.confirm}
              onChange={e => set('confirm', e.target.value)}
              onBlur={() => blur('confirm')}
              error={errors.confirm}
              icon={Lock}
              autoComplete="new-password"
              placeholder="••••••••"
              rightElement={
                <button
                  type="button"
                  onClick={() => setShowConfirm(v => !v)}
                  className="text-slate-500 hover:text-slate-300 transition-colors p-0.5 rounded"
                  aria-label={showConfirm ? 'Hide password' : 'Show password'}
                >
                  {showConfirm ? <EyeOff size={16} /> : <Eye size={16} />}
                </button>
              }
            />

            {/* Submit */}
            <button
              id="register-submit-btn"
              type="submit"
              disabled={loading || !!successMsg}
              className="btn-primary w-full justify-center py-3.5 text-base mt-1"
            >
              {loading ? (
                <><Loader2 size={18} className="animate-spin" /> Creating account…</>
              ) : (
                <><UserPlus size={18} /> Create Account</>
              )}
            </button>
          </form>

          {/* Sign in link */}
          <p className="text-center text-sm text-slate-500">
            Already have an account?{' '}
            <Link
              to="/login"
              id="signin-link"
              className="text-primary-400 hover:text-primary-300 font-medium transition-colors hover:underline underline-offset-2"
            >
              Sign In
            </Link>
          </p>
        </div>
      </div>
    </div>
  );
}
