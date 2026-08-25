// src/App.jsx
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import NavBar from './components/NavBar';
import ProtectedRoute from './components/ProtectedRoute';
import Home from './pages/Home';
import AnalyzeImage from './pages/AnalyzeImage';
import AnalyzeVideo from './pages/AnalyzeVideo';
import AnalyzeURL from './pages/AnalyzeURL';
import Results from './pages/Results';
import History from './pages/History';
import About from './pages/About';
import Dashboard from './pages/Dashboard';
import Login from './pages/Login';
import Register from './pages/Register';
import ForgotPassword from './pages/ForgotPassword';
import ResetPassword from './pages/ResetPassword';
import { ToastProvider } from './context/ToastContext';
import { AuthProvider } from './context/AuthContext';
import { ShieldCheck } from 'lucide-react';

function Footer() {
  return (
    <footer className="border-t border-surface-border mt-24 py-8">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex flex-col sm:flex-row items-center justify-between gap-4">
          <div className="flex items-center gap-2.5">
            <div className="w-6 h-6 rounded-md bg-gradient-to-br from-primary-500 to-accent flex items-center justify-center">
              <ShieldCheck size={13} className="text-white" />
            </div>
            <span className="text-slate-400 text-sm font-medium">
              Trust<span className="text-primary-400">AI</span>
            </span>
          </div>
          <p className="text-slate-500 text-sm text-center">
            Multimodal Digital Content Trust System &nbsp;·&nbsp;
            <span className="text-primary-500">Decision-support tool, not a truth oracle.</span>
          </p>
          <p className="text-slate-600 text-xs">v1.0.0</p>
        </div>
      </div>
    </footer>
  );
}

/** Layout used by all authenticated app pages (with NavBar + Footer). */
function AppLayout({ children }) {
  return (
    <div className="min-h-screen flex flex-col">
      <NavBar />
      <div className="flex-1">{children}</div>
      <Footer />
    </div>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <ToastProvider>
          <Routes>
            {/* ── Public auth routes — no NavBar/Footer ── */}
            <Route path="/login" element={<Login />} />
            <Route path="/register" element={<Register />} />
            <Route path="/forgot-password" element={<ForgotPassword />} />
            <Route path="/reset-password" element={<ResetPassword />} />

            {/* ── Protected: all existing routes — require authentication ── */}
            <Route
              path="/"
              element={
                <ProtectedRoute>
                  <AppLayout><Home /></AppLayout>
                </ProtectedRoute>
              }
            />
            <Route
              path="/dashboard"
              element={
                <ProtectedRoute>
                  <AppLayout><Dashboard /></AppLayout>
                </ProtectedRoute>
              }
            />
            <Route
              path="/analyze/image"
              element={
                <ProtectedRoute>
                  <AppLayout><AnalyzeImage /></AppLayout>
                </ProtectedRoute>
              }
            />
            <Route
              path="/analyze/video"
              element={
                <ProtectedRoute>
                  <AppLayout><AnalyzeVideo /></AppLayout>
                </ProtectedRoute>
              }
            />
            <Route
              path="/analyze/url"
              element={
                <ProtectedRoute>
                  <AppLayout><AnalyzeURL /></AppLayout>
                </ProtectedRoute>
              }
            />
            <Route
              path="/results"
              element={
                <ProtectedRoute>
                  <AppLayout><Results /></AppLayout>
                </ProtectedRoute>
              }
            />
            <Route
              path="/history"
              element={
                <ProtectedRoute>
                  <AppLayout><History /></AppLayout>
                </ProtectedRoute>
              }
            />
            <Route
              path="/about"
              element={
                <ProtectedRoute>
                  <AppLayout><About /></AppLayout>
                </ProtectedRoute>
              }
            />
            {/* ── Catch-all fallback ── */}
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </ToastProvider>
      </AuthProvider>
    </BrowserRouter>
  );
}
