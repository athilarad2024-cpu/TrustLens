// context/AuthContext.jsx
// Global authentication state for TrustAI.
// Stores the JWT token in sessionStorage (clears on browser close).
// Provides login(), logout(), and user state to all components.

import { createContext, useCallback, useContext, useMemo, useState } from 'react';

const AuthContext = createContext(null);

const STORAGE_KEY = 'trustai_auth';

function loadStored() {
  try {
    const raw = sessionStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    // Validate the token hasn't expired (JWT exp is in seconds)
    if (parsed?.token) {
      const [, payload] = parsed.token.split('.');
      const decoded = JSON.parse(atob(payload));
      if (decoded.exp && Date.now() / 1000 > decoded.exp) {
        sessionStorage.removeItem(STORAGE_KEY);
        return null;
      }
    }
    return parsed;
  } catch {
    return null;
  }
}

export function AuthProvider({ children }) {
  const [auth, setAuth] = useState(() => loadStored());

  const login = useCallback((token, user) => {
    const state = { token, user };
    sessionStorage.setItem(STORAGE_KEY, JSON.stringify(state));
    setAuth(state);
  }, []);

  const logout = useCallback(() => {
    sessionStorage.removeItem(STORAGE_KEY);
    setAuth(null);
  }, []);

  const value = useMemo(
    () => ({ isAuthenticated: !!auth, token: auth?.token ?? null, user: auth?.user ?? null, login, logout }),
    [auth, login, logout]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used inside <AuthProvider>');
  return ctx;
}
