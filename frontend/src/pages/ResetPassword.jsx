// pages/ResetPassword.jsx
// Reads ?token=... from the URL query string and POSTs the new password.
import { useState } from 'react';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import {
  ShieldCheck, Lock, Eye, EyeOff,
  AlertCircle, CheckCircle2, Loader2, KeyRound, ArrowLeft,
} from 'lucide-react';
import { resetPassword } from '../services/api';

function BgOrbs() {
  return (
    <div className="pointer-events-none fixed inset-0 overflow-hidden -z-10" aria-hidden>
      <div
        className="absolute -top-40 right-0 w-96 h-96 rounded-full opacity-20 blur-3xl"
        style={{ background: 'radial-gradient(circle, #6366f1 0%, transparent 70%)' }}
      />
      <div
        className="absolute -bottom-32 -left-32 w-80 h-80 rounded-full opacity-15 blur-3xl animate-float"
        style={{ background: 'radial-gradient(circle, #06b6d4 0%, transparent 70%)' }}
      />
    </div>
  );
}

function InputField({ id, label, type, value, onChange, onBlur, error, rightElement, autoComplete, placeholder }) {
  return (
    <div className="space-y-1.5">
      <label htmlFor={id} className="label">{label}</label>
      <div className="relative">
        <div className="absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-500 pointer-events-none">
          <Lock size={16} />
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

const STRENGTH_RULES = [
  { label: 'At least 8 characters', test: p => p.length >= 8 },
  { label: 'One uppercase letter',  test: p => /[A-Z]/.test(p) },
  { label: 'One lowercase letter',  test: p => /[a-z]/.test(p) },
  { label: 'One number',            test: p => /\d/.test(p) },
];

export default function ResetPassword() {
  const [searchParams] = useSearchParams();
  const navigate = useNavigate();
  const token = searchParams.get('token') || '';

  const [newPassword, setNewPassword]     = useState('');
  const [confirm, setConfirm]             = useState('');
  const [showNew, setShowNew]             = useState(false);
  const [showConfirm, setShowConfirm]     = useState(false);
  const [touched, setTouched]             = useState({ new: false, confirm: false });
  const [loading, setLoading]             = useState(false);
  const [serverError, setServerError]     = useState('');
  const [success, setSuccess]             = useState(false);

  // No token in URL — show clear error immediately
  if (!token) {
    return (
      <div className="min-h-screen flex items-center justify-center px-4 py-12 relative">
        <BgOrbs />
        <div className="w-full max-w-md animate-slide-up">
          <div className="card-glass p-8 sm:p-10 space-y-6 text-center">
            <div className="w-14 h-14 rounded-full bg-red-500/10 border border-red-500/30 flex items-center justify-center mx-auto">
              <AlertCircle size={28} className="text-red-400" />
            </div>
            <div>
              <h1 className="text-xl font-bold text-white">Invalid reset link</h1>
              <p className="text-slate-400 text-sm mt-2 leading-relaxed">
                This password reset link is invalid or missing a token.
                Please request a new one.
              </p>
            </div>
            <Link to="/forgot-password" className="btn-primary justify-center w-full py-3">
              Request new link
            </Link>
          </div>
        </div>
      </div>
    );
  }

  // ── Validation ──────────────────────────────────────────────────────────────
  const newError = (() => {
    if (!touched.new) return '';
    if (!newPassword) return 'New password is required.';
    if (newPassword.length < 8) return 'Password must be at least 8 characters.';
    if (!/[A-Z]/.test(newPassword)) return 'Password must contain an uppercase letter.';
    if (!/[a-z]/.test(newPassword)) return 'Password must contain a lowercase letter.';
    if (!/\d/.test(newPassword)) return 'Password must contain a number.';
    return '';
  })();

  const confirmError = (() => {
    if (!touched.confirm) return '';
    if (!confirm) return 'Please confirm your new password.';
    if (confirm !== newPassword) return 'Passwords do not match.';
    return '';
  })();

  const isStrong = STRENGTH_RULES.every(r => r.test(newPassword));
  const isFormValid = isStrong && confirm === newPassword && newPassword;

  // ── Submit ──────────────────────────────────────────────────────────────────
  async function handleSubmit(e) {
    e.preventDefault();
    setTouched({ new: true, confirm: true });
    if (!isFormValid) return;

    setLoading(true);
    setServerError('');

    try {
      const data = await resetPassword(token, newPassword, confirm);
      setSuccess(true);
      setTimeout(() => navigate('/login'), 3000);
    } catch (err) {
      setServerError(err?.message || 'This link is invalid or has expired. Please request a new one.');
    } finally {
      setLoading(false);
    }
  }

  // ── Success state ───────────────────────────────────────────────────────────
  if (success) {
    return (
      <div className="min-h-screen flex items-center justify-center px-4 py-12 relative">
        <BgOrbs />
        <div className="w-full max-w-md animate-slide-up">
          <div className="card-glass p-8 sm:p-10 space-y-6 text-center">
            <div className="w-16 h-16 rounded-full bg-emerald-500/10 border border-emerald-500/30 flex items-center justify-center mx-auto">
              <CheckCircle2 size={32} className="text-emerald-400" />
            </div>
            <div>
              <h1 className="text-xl font-bold text-white">Password updated!</h1>
              <p className="text-slate-400 text-sm mt-2 leading-relaxed">
                Your password has been changed successfully.
                You'll be redirected to the sign-in page in a moment.
              </p>
            </div>
            <Link to="/login" className="btn-primary justify-center w-full py-3">
              Sign In now
            </Link>
          </div>
        </div>
      </div>
    );
  }

  // ── Form ────────────────────────────────────────────────────────────────────
  const passedRules = STRENGTH_RULES.filter(r => r.test(newPassword)).length;
  const barColors = ['bg-red-500', 'bg-orange-500', 'bg-amber-400', 'bg-emerald-500'];

  return (
    <div className="min-h-screen flex items-center justify-center px-4 py-12 relative">
      <BgOrbs />

      <div className="w-full max-w-md animate-slide-up" style={{ animationFillMode: 'both' }}>
        <div className="card-glass p-8 sm:p-10 space-y-8">

          {/* Branding */}
          <div className="flex flex-col items-center gap-3 text-center">
            <div className="relative">
              <div className="w-14 h-14 rounded-2xl bg-gradient-to-br from-primary-500 to-accent flex items-center justify-center shadow-2xl shadow-primary-900/60">
                <ShieldCheck size={28} className="text-white" />
              </div>
              <div className="absolute inset-0 rounded-2xl border border-primary-400/30 scale-110" />
            </div>
            <div>
              <h1 className="text-2xl font-bold tracking-tight text-white">Choose a new password</h1>
              <p className="text-slate-400 text-sm mt-1">Make it strong and memorable.</p>
            </div>
          </div>

          {/* Form */}
          <form onSubmit={handleSubmit} noValidate className="space-y-5">
            {serverError && (
              <div className="flex items-start gap-3 rounded-xl border border-red-500/30 bg-red-950/40 px-4 py-3 animate-slide-in-down" role="alert">
                <AlertCircle size={16} className="text-red-400 flex-shrink-0 mt-0.5" />
                <p className="text-red-300 text-sm leading-relaxed">{serverError}</p>
              </div>
            )}

            {/* New password */}
            <div>
              <InputField
                id="reset-new-password"
                label="New Password"
                type={showNew ? 'text' : 'password'}
                value={newPassword}
                onChange={e => { setNewPassword(e.target.value); setServerError(''); }}
                onBlur={() => setTouched(t => ({ ...t, new: true }))}
                error={newError}
                autoComplete="new-password"
                placeholder="••••••••"
                rightElement={
                  <button
                    type="button"
                    onClick={() => setShowNew(v => !v)}
                    className="text-slate-500 hover:text-slate-300 transition-colors p-0.5 rounded"
                    aria-label={showNew ? 'Hide password' : 'Show password'}
                  >
                    {showNew ? <EyeOff size={16} /> : <Eye size={16} />}
                  </button>
                }
              />

              {/* Strength bar + checklist */}
              {(touched.new && newPassword) && (
                <div className="space-y-2 pt-2">
                  <div className="flex gap-1">
                    {STRENGTH_RULES.map((_, i) => (
                      <div
                        key={i}
                        className={`h-1 flex-1 rounded-full transition-all duration-300 ${
                          i < passedRules ? barColors[passedRules - 1] : 'bg-surface-border'
                        }`}
                      />
                    ))}
                  </div>
                  <ul className="space-y-0.5">
                    {STRENGTH_RULES.map(rule => {
                      const ok = rule.test(newPassword);
                      return (
                        <li key={rule.label} className={`flex items-center gap-1.5 text-xs ${ok ? 'text-emerald-400' : 'text-slate-500'}`}>
                          <CheckCircle2 size={11} className={ok ? 'text-emerald-400' : 'text-slate-600'} />
                          {rule.label}
                        </li>
                      );
                    })}
                  </ul>
                </div>
              )}
            </div>

            {/* Confirm password */}
            <InputField
              id="reset-confirm-password"
              label="Confirm New Password"
              type={showConfirm ? 'text' : 'password'}
              value={confirm}
              onChange={e => { setConfirm(e.target.value); setServerError(''); }}
              onBlur={() => setTouched(t => ({ ...t, confirm: true }))}
              error={confirmError}
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
              id="reset-submit-btn"
              type="submit"
              disabled={loading}
              className="btn-primary w-full justify-center py-3.5 text-base mt-1"
            >
              {loading ? (
                <><Loader2 size={18} className="animate-spin" /> Updating password…</>
              ) : (
                <><KeyRound size={18} /> Update Password</>
              )}
            </button>

            <div className="text-center">
              <Link
                to="/login"
                className="inline-flex items-center gap-1.5 text-sm text-slate-500 hover:text-slate-300 transition-colors"
              >
                <ArrowLeft size={14} />
                Back to Sign In
              </Link>
            </div>
          </form>
        </div>
      </div>
    </div>
  );
}
