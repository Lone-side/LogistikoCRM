import { Suspense, lazy, useEffect, useState } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { useAuthStore } from './stores/authStore';
import { Layout, ErrorBoundary } from './components';
import { ToastProvider } from './components/Toast';

// Το Login μένει eager: είναι η πρώτη οθόνη για μη συνδεδεμένο χρήστη και
// ένα lazy chunk εδώ θα πρόσθετε round-trip στο critical path.
import Login from './pages/Login';

// Όλες οι υπόλοιπες σελίδες φορτώνουν κατ' απαίτηση (route-level code
// splitting) — αλλιώς κάθε χρήστης κατεβάζει ολόκληρη την εφαρμογή για να
// δει το dashboard.
const Dashboard = lazy(() => import('./pages/Dashboard'));
const Clients = lazy(() => import('./pages/Clients'));
const ClientDetails = lazy(() => import('./pages/ClientDetails'));
const Obligations = lazy(() => import('./pages/Obligations'));
const Calendar = lazy(() => import('./pages/Calendar'));
const Files = lazy(() => import('./pages/Files'));
const Calls = lazy(() => import('./pages/Calls'));
const Tickets = lazy(() => import('./pages/Tickets'));
// ΠΡΟΣΟΧΗ: το barrel pages/index.ts εξάγει το `Emails` από το
// ./EmailTemplates (όχι από το ./Emails) — διατηρείται η ίδια αντιστοίχιση.
const Emails = lazy(() => import('./pages/EmailTemplates'));
const EmailSettings = lazy(() => import('./pages/EmailSettings'));
const Reports = lazy(() => import('./pages/Reports'));
const Settings = lazy(() => import('./pages/Settings'));
const ObligationSettings = lazy(() => import('./pages/ObligationSettings'));
const UserManagement = lazy(() => import('./pages/UserManagement'));
const MyData = lazy(() => import('./pages/MyData'));
const Backup = lazy(() => import('./pages/Backup'));
const FileManager = lazy(() => import('./pages/FileManager'));
const FilingSettings = lazy(() => import('./pages/FilingSettings'));
const SharedLinkPortal = lazy(() => import('./pages/SharedLinkPortal'));

function FullPageSpinner() {
  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50">
      <div
        className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"
        role="status"
        aria-label="Φόρτωση"
      ></div>
    </div>
  );
}

// Create a client for React Query
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 5 * 60 * 1000, // 5 minutes
      retry: 1,
    },
  },
});

// Protected Route wrapper with Layout
function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const isAuthenticated = useAuthStore((state) => state.isAuthenticated);
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
    return <FullPageSpinner />;
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  return <Layout>{children}</Layout>;
}

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <ErrorBoundary>
        <ToastProvider>
          <BrowserRouter>
          <Suspense fallback={<FullPageSpinner />}>
          <Routes>
          {/* Public routes */}
          <Route path="/login" element={<Login />} />
          <Route path="/share/:token" element={<SharedLinkPortal />} />

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
          </Suspense>
          </BrowserRouter>
        </ToastProvider>
      </ErrorBoundary>
    </QueryClientProvider>
  );
}

export default App;
