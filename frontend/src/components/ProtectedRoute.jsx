// components/ProtectedRoute.jsx
// Wraps protected pages: redirects to /login when user is not authenticated.
import { Navigate, useLocation } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';

export default function ProtectedRoute({ children }) {
  const { isAuthenticated } = useAuth();
  const location = useLocation();

  if (!isAuthenticated) {
    // Pass the attempted path so Login can redirect back after auth
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  return children;
}
