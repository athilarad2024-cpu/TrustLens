// pages/ForgotPassword.jsx
import { useState } from 'react';
import { Link } from 'react-router-dom';
import { ShieldCheck, Mail, Send, AlertCircle, CheckCircle2, Loader2, ArrowLeft } from 'lucide-react';
import { forgotPassword } from '../services/api';

function BgOrbs() {
  return (
    <div className="pointer-events-none fixed inset-0 overflow-hidden -z-10" aria-hidden>
      <div
        className="absolute -top-40 -left-40 w-96 h-96 rounded-full opacity-20 blur-3xl"
        style={{ background: 'radial-gradient(circle, #6366f1 0%, transparent 70%)' }}
      />
      <div
        className="absolute -bottom-32 right-0 w-80 h-80 rounded-full opacity-15 blur-3xl animate-float"
        style={{ background: 'radial-gradient(circle, #06b6d4 0%, transparent 70%)' }}
      />
    </div>
  );
}

export default function ForgotPassword() {
  const [email, setEmail]           = useState('');
  const [touched, setTouched]       = useState(false);
  const [loading, setLoading]       = useState(false);
  const [serverError, setServerError] = useState('');
  const [submitted, setSubmitted]   = useState(false);

  const emailError = (() => {
    if (!touched) return '';
    if (!email.trim()) return 'Email is required.';
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) return 'Please enter a valid email address.';
    return '';
  })();

  async function handleSubmit(e) {
    e.preventDefault();
    setTouched(true);
    if (emailError || !email.trim()) return;

    setLoading(true);
    setServerError('');

    try {
      await forgotPassword(email.trim());
      // Always show generic success — do NOT reveal whether account exists
      setSubmitted(true);
    } catch (err) {
      // Network/server error — still generic to avoid enumeration
      setServerError('Something went wrong. Please try again later.');
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
          <div className="flex flex-col items-center gap-3 text-center">
            <div className="relative">
              <div className="w-14 h-14 rounded-2xl bg-gradient-to-br from-primary-500 to-accent flex items-center justify-center shadow-2xl shadow-primary-900/60">
                <ShieldCheck size={28} className="text-white" />
              </div>
              <div className="absolute inset-0 rounded-2xl border border-primary-400/30 scale-110" />
            </div>
            <div>
              <h1 className="text-2xl font-bold tracking-tight text-white">Reset your password</h1>
              <p className="text-slate-400 text-sm mt-1">
                Enter your email and we'll send a reset link.
              </p>
            </div>
          </div>

          {/* ── Success state ─────────────────────────────────────── */}
          {submitted ? (
            <div className="space-y-6">
              <div className="flex flex-col items-center gap-4 text-center py-4">
                <div className="w-14 h-14 rounded-full bg-emerald-500/10 border border-emerald-500/30 flex items-center justify-center">
                  <CheckCircle2 size={28} className="text-emerald-400" />
                </div>
                <div>
                  <p className="text-slate-200 font-semibold">Check your inbox</p>
                  <p className="text-slate-400 text-sm mt-2 leading-relaxed">
                    If an account exists for{' '}
                    <span className="text-slate-300 font-medium">{email}</span>,
                    a password reset link has been sent.
                  </p>
                  <p className="text-slate-500 text-xs mt-3">
                    The link expires in 30 minutes and can only be used once.
                  </p>
                </div>
              </div>
              <Link
                to="/login"
                className="btn-secondary w-full justify-center py-3"
              >
                <ArrowLeft size={16} />
                Back to Sign In
              </Link>
            </div>
          ) : (
            /* ── Form state ─────────────────────────────────────────── */
            <form onSubmit={handleSubmit} noValidate className="space-y-5">
              {serverError && (
                <div className="flex items-start gap-3 rounded-xl border border-red-500/30 bg-red-950/40 px-4 py-3 animate-slide-in-down" role="alert">
                  <AlertCircle size={16} className="text-red-400 flex-shrink-0 mt-0.5" />
                  <p className="text-red-300 text-sm leading-relaxed">{serverError}</p>
                </div>
              )}

              {/* Email field */}
              <div className="space-y-1.5">
                <label htmlFor="forgot-email" className="label">Email Address</label>
                <div className="relative">
                  <div className="absolute left-3.5 top-1/2 -translate-y-1/2 text-slate-500 pointer-events-none">
                    <Mail size={16} />
                  </div>
                  <input
                    id="forgot-email"
                    type="email"
                    value={email}
                    onChange={e => { setEmail(e.target.value); setServerError(''); }}
                    onBlur={() => setTouched(true)}
                    autoComplete="email"
                    placeholder="you@example.com"
                    className={`input-field pl-10 transition-all duration-200 ${
                      emailError
                        ? 'border-red-500/70 focus:ring-red-500/50 bg-red-950/10'
                        : 'border-surface-border focus:border-primary-500/50'
                    }`}
                  />
                </div>
                {emailError && (
                  <p className="flex items-center gap-1.5 text-xs text-red-400 animate-slide-in-down" role="alert">
                    <AlertCircle size={12} className="flex-shrink-0" />
                    {emailError}
                  </p>
                )}
              </div>

              {/* Submit */}
              <button
                id="forgot-submit-btn"
                type="submit"
                disabled={loading}
                className="btn-primary w-full justify-center py-3.5 text-base"
              >
                {loading ? (
                  <><Loader2 size={18} className="animate-spin" /> Sending…</>
                ) : (
                  <><Send size={18} /> Send Reset Link</>
                )}
              </button>

              {/* Back link */}
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
          )}
        </div>
      </div>
    </div>
  );
}
