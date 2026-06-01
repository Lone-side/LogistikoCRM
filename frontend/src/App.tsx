import { useEffect, useState } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { useAuthStore } from './stores/authStore';
import { Layout, ErrorBoundary } from './components';
import { ToastProvider } from './components/Toast';

// Pages
import {
  Dashboard,
  Login,
  Clients,
  ClientDetails,
  Obligations,
  Calendar,
  Files,
  Calls,
  Tickets,
  Emails,
  EmailSettings,
  Reports,
  Settings,
  ObligationSettings,
  UserManagement,
  MyData,
} from './pages';
import Backup from './pages/Backup';
import FileManager from './pages/FileManager';
import FilingSettings from './pages/FilingSettings';
import SharedLinkPortal from './pages/SharedLinkPortal';
import AccountantDashboard from './pages/AccountantDashboard';
import ClientPortal from './pages/ClientPortal';
import SetPassword from './pages/SetPassword';

// Create a client for React Query
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 5 * 60 * 1000, // 5 minutes
      retry: 1,
    },
  },
});

// Protected Route wrapper with Layout (staff). Clients are redirected to /portal.
function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated);
  const user = useAuthStore((state) => state.user);
  const checkAuth = useAuthStore((state) => state.checkAuth);
  const [isChecking, setIsChecking] = useState(true);

  useEffect(() => {
    const verify = async () => {
      await checkAuth();
      setIsChecking(false);
    };
    verify();
  }, [checkAuth]);

  if (isChecking) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
      </div>
    );
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  // Client users δεν έχουν πρόσβαση στο staff UI — redirect στην πύλη πελάτη.
  if (user?.is_client) {
    return <Navigate to="/portal" replace />;
  }

  return <Layout>{children}</Layout>;
}

// Client Portal route wrapper. Μόνο για client users· staff πάει στο dashboard.
function ClientRoute({ children }: { children: React.ReactNode }) {
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated);
  const user = useAuthStore((state) => state.user);
  const checkAuth = useAuthStore((state) => state.checkAuth);
  const [isChecking, setIsChecking] = useState(true);

  useEffect(() => {
    const verify = async () => {
      await checkAuth();
      setIsChecking(false);
    };
    verify();
  }, [checkAuth]);

  if (isChecking) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
      </div>
    );
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  // Staff users δεν χρειάζονται την πύλη πελάτη — πάνε στο dashboard.
  if (!user?.is_client) {
    return <Navigate to="/dashboard" replace />;
  }

  return <>{children}</>;
}

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <ErrorBoundary>
        <ToastProvider>
          <BrowserRouter>
          <Routes>
          {/* Public routes */}
          <Route path="/login" element={<Login />} />
          <Route path="/set-password" element={<SetPassword />} />
          <Route path="/share/:token" element={<SharedLinkPortal />} />

          {/* Full-bleed showcase dashboard — no Layout wrapper */}
          <Route path="/dashboard-v2" element={<AccountantDashboard />} />

          {/* Client Portal — δική του layout, μόνο για client users */}
          <Route
            path="/portal"
            element={
              <ClientRoute>
                <ClientPortal />
              </ClientRoute>
            }
          />

          {/* Protected routes with Layout */}
          <Route
            path="/"
            element={
              <ProtectedRoute>
                <Dashboard />
              </ProtectedRoute>
            }
          />
          <Route
            path="/dashboard"
            element={
              <ProtectedRoute>
                <Dashboard />
              </ProtectedRoute>
            }
          />
          <Route
            path="/clients"
            element={
              <ProtectedRoute>
                <Clients />
              </ProtectedRoute>
            }
          />
          <Route
            path="/clients/:id"
            element={
              <ProtectedRoute>
                <ClientDetails />
              </ProtectedRoute>
            }
          />
          <Route
            path="/obligations"
            element={
              <ProtectedRoute>
                <Obligations />
              </ProtectedRoute>
            }
          />
          <Route
            path="/calendar"
            element={
              <ProtectedRoute>
                <Calendar />
              </ProtectedRoute>
            }
          />
          <Route
            path="/files"
            element={
              <ProtectedRoute>
                <Files />
              </ProtectedRoute>
            }
          />
          <Route
            path="/file-manager"
            element={
              <ProtectedRoute>
                <FileManager />
              </ProtectedRoute>
            }
          />
          <Route
            path="/calls"
            element={
              <ProtectedRoute>
                <Calls />
              </ProtectedRoute>
            }
          />
          <Route
            path="/tickets"
            element={
              <ProtectedRoute>
                <Tickets />
              </ProtectedRoute>
            }
          />
          <Route
            path="/emails"
            element={
              <ProtectedRoute>
                <Emails />
              </ProtectedRoute>
            }
          />
          <Route
            path="/reports"
            element={
              <ProtectedRoute>
                <Reports />
              </ProtectedRoute>
            }
          />
          <Route
            path="/mydata"
            element={
              <ProtectedRoute>
                <MyData />
              </ProtectedRoute>
            }
          />
          <Route
            path="/settings"
            element={
              <ProtectedRoute>
                <Settings />
              </ProtectedRoute>
            }
          />
          <Route
            path="/settings/obligations"
            element={
              <ProtectedRoute>
                <ObligationSettings />
              </ProtectedRoute>
            }
          />
          <Route
            path="/settings/users"
            element={
              <ProtectedRoute>
                <UserManagement />
              </ProtectedRoute>
            }
          />
          <Route
            path="/settings/backup"
            element={
              <ProtectedRoute>
                <Backup />
              </ProtectedRoute>
            }
          />
          <Route
            path="/settings/email"
            element={
              <ProtectedRoute>
                <EmailSettings />
              </ProtectedRoute>
            }
          />
          <Route
            path="/settings/filing"
            element={
              <ProtectedRoute>
                <FilingSettings />
              </ProtectedRoute>
            }
          />

          {/* Redirect unknown routes to dashboard */}
          <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
          </BrowserRouter>
        </ToastProvider>
      </ErrorBoundary>
    </QueryClientProvider>
  );
}

export default App;
