import { useEffect, useState } from 'react';
import { Navigate, useLocation } from 'react-router-dom';
import { useAuthStore } from '../stores/authStore';
import { Layout, ErrorBoundary } from '../components';

// Κοινό spinner όσο ελέγχεται το auth state.
function AuthChecking() {
  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50">
      <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-brand-600"></div>
    </div>
  );
}

// Κοινό hook: τρέχει checkAuth() μία φορά και επιστρέφει αν ολοκληρώθηκε.
function useAuthCheck() {
  const checkAuth = useAuthStore((state) => state.checkAuth);
  const [isChecking, setIsChecking] = useState(true);
  useEffect(() => {
    let active = true;
    (async () => {
      await checkAuth();
      if (active) setIsChecking(false);
    })();
    return () => {
      active = false;
    };
  }, [checkAuth]);
  return isChecking;
}

/**
 * Staff route: απαιτεί authentication. Οι πελάτες (is_client) ανακατευθύνονται
 * στην πύλη τους· οι μη-συνδεδεμένοι στο /login. Τυλίγει το παιδί σε Layout.
 */
export function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated);
  const user = useAuthStore((state) => state.user);
  const isChecking = useAuthCheck();
  const location = useLocation();

  if (isChecking) return <AuthChecking />;
  if (!isAuthenticated) return <Navigate to="/login" replace />;
  if (user?.is_client) return <Navigate to="/portal" replace />;
  // Per-route boundary: a page crash shows a fallback (Layout/nav survive) and
  // clears on navigation (resetKeys=[path]).
  return (
    <Layout>
      <ErrorBoundary compact resetKeys={[location.pathname]}>
        {children}
      </ErrorBoundary>
    </Layout>
  );
}

/**
 * Client portal route: μόνο για client users. Staff → /dashboard,
 * μη-συνδεδεμένοι → /login.
 */
export function ClientRoute({ children }: { children: React.ReactNode }) {
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated);
  const user = useAuthStore((state) => state.user);
  const isChecking = useAuthCheck();
  const location = useLocation();

  if (isChecking) return <AuthChecking />;
  if (!isAuthenticated) return <Navigate to="/login" replace />;
  if (!user?.is_client) return <Navigate to="/dashboard" replace />;
  return (
    <ErrorBoundary compact resetKeys={[location.pathname]}>
      {children}
    </ErrorBoundary>
  );
}
