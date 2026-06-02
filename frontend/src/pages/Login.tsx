import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuthStore } from '../stores/authStore';
import { portalApi } from '../api/client';
import { LogIn, AlertCircle } from 'lucide-react';

export default function Login() {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [rememberMe, setRememberMe] = useState(true);
  const { login, isLoading, error, clearError } = useAuthStore();
  const navigate = useNavigate();

  // Self-service «ξέχασα τον κωδικό» (πελάτες).
  const [showReset, setShowReset] = useState(false);
  const [resetId, setResetId] = useState('');
  const [resetMsg, setResetMsg] = useState('');
  const [resetBusy, setResetBusy] = useState(false);

  const handleReset = async (e: React.FormEvent) => {
    e.preventDefault();
    setResetBusy(true);
    setResetMsg('');
    try {
      const res = await portalApi.requestPasswordReset(resetId);
      setResetMsg(res.detail || 'Αν υπάρχει λογαριασμός, στάλθηκε σύνδεσμος.');
    } catch {
      // Γενικό μήνυμα — δεν αποκαλύπτουμε αν υπάρχει λογαριασμός.
      setResetMsg('Αν υπάρχει λογαριασμός, στάλθηκε σύνδεσμος στο email σας.');
    } finally {
      setResetBusy(false);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    clearError();

    try {
      await login(username, password, rememberMe);
      // Route ανάλογα με τον ρόλο: πελάτες στην πύλη, staff στο dashboard.
      const user = useAuthStore.getState().user;
      navigate(user?.is_client ? '/portal' : '/dashboard');
    } catch {
      // Error is handled in the store
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-100 py-12 px-4 sm:px-6 lg:px-8">
      <div className="max-w-md w-full space-y-8">
        <div>
          <h1 className="text-center text-3xl font-bold text-gray-900">
            LogistikoCRM
          </h1>
          <h2 className="mt-2 text-center text-lg text-gray-600">
            Σύνδεση στο λογαριασμό σας
          </h2>
        </div>

        <form className="mt-8 space-y-6" onSubmit={handleSubmit}>
          {error && (
            <div className="rounded-md bg-red-50 p-4">
              <div className="flex">
                <AlertCircle className="h-5 w-5 text-red-400" />
                <div className="ml-3">
                  <p className="text-sm text-red-700">{error}</p>
                </div>
              </div>
            </div>
          )}

          <div className="space-y-4">
            <div>
              <label htmlFor="username" className="block text-sm font-medium text-gray-700">
                Όνομα χρήστη
              </label>
              <input
                id="username"
                name="username"
                type="text"
                autoComplete="username"
                required
                value={username}
                onChange={(e) => setUsername(e.target.value)}
                className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm placeholder-gray-400 focus:outline-none focus:ring-blue-500 focus:border-blue-500"
                placeholder="Εισάγετε το όνομα χρήστη"
              />
            </div>

            <div>
              <label htmlFor="password" className="block text-sm font-medium text-gray-700">
                Κωδικός
              </label>
              <input
                id="password"
                name="password"
                type="password"
                autoComplete="current-password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm placeholder-gray-400 focus:outline-none focus:ring-blue-500 focus:border-blue-500"
                placeholder="Εισάγετε τον κωδικό"
              />
            </div>
          </div>

          <div className="flex items-center justify-between">
            <div className="flex items-center">
              <input
                id="remember-me"
                name="remember-me"
                type="checkbox"
                checked={rememberMe}
                onChange={(e) => setRememberMe(e.target.checked)}
                className="h-4 w-4 text-blue-600 focus:ring-blue-500 border-gray-300 rounded cursor-pointer"
              />
              <label htmlFor="remember-me" className="ml-2 block text-sm text-gray-700 cursor-pointer">
                Να με θυμάσαι
              </label>
            </div>
          </div>

          <div>
            <button
              type="submit"
              disabled={isLoading}
              className="group relative w-full flex justify-center py-2 px-4 border border-transparent text-sm font-medium rounded-md text-white bg-blue-600 hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-blue-500 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <span className="absolute left-0 inset-y-0 flex items-center pl-3">
                <LogIn className="h-5 w-5 text-blue-500 group-hover:text-blue-400" />
              </span>
              {isLoading ? 'Σύνδεση...' : 'Σύνδεση'}
            </button>
          </div>
        </form>

        {/* Self-service ξέχασα τον κωδικό (πελάτες) */}
        <div className="text-center">
          <button
            type="button"
            onClick={() => { setShowReset((v) => !v); setResetMsg(''); }}
            className="text-sm text-blue-600 hover:text-blue-700"
          >
            Ξέχασα τον κωδικό μου
          </button>
        </div>

        {showReset && (
          <form onSubmit={handleReset} className="space-y-3 border-t border-gray-200 pt-4">
            <label htmlFor="reset-id" className="block text-sm text-gray-600">
              Δώστε το email ή το ΑΦΜ σας — θα σας σταλεί σύνδεσμος ορισμού κωδικού.
            </label>
            <div className="flex gap-2">
              <input
                id="reset-id"
                type="text"
                value={resetId}
                onChange={(e) => setResetId(e.target.value)}
                placeholder="Email ή ΑΦΜ"
                className="flex-1 px-3 py-2 border border-gray-300 rounded-md text-sm focus:outline-none focus:ring-blue-500 focus:border-blue-500"
              />
              <button
                type="submit"
                disabled={resetBusy || resetId.length === 0}
                className="px-4 py-2 text-sm font-medium rounded-md text-white bg-blue-600 hover:bg-blue-700 disabled:opacity-50"
              >
                {resetBusy ? 'Αποστολή…' : 'Αποστολή'}
              </button>
            </div>
            {resetMsg && (
              <p role="status" className="text-sm text-gray-700 bg-gray-50 border border-gray-200 rounded-md p-2">
                {resetMsg}
              </p>
            )}
          </form>
        )}
      </div>
    </div>
  );
}
