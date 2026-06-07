import { useState, useEffect } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { AlertCircle, CheckCircle, KeyRound } from 'lucide-react';
import { apiClient } from '../api/client';

export default function SetPassword() {
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const uid = params.get('uid') || '';
  const token = params.get('token') || '';

  const [password, setPassword] = useState('');
  const [confirm, setConfirm] = useState('');
  const [error, setError] = useState('');
  const [done, setDone] = useState(false);
  const [loading, setLoading] = useState(false);

  const linkMissing = !uid || !token;

  // Redirect μετά την επιτυχία, με καθαρισμό του timer αν ξεφορτωθεί το component.
  useEffect(() => {
    if (!done) return;
    const t = setTimeout(() => navigate('/login'), 2500);
    return () => clearTimeout(t);
  }, [done, navigate]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');

    if (password.length < 8) {
      setError('Ο κωδικός πρέπει να έχει τουλάχιστον 8 χαρακτήρες.');
      return;
    }
    if (password !== confirm) {
      setError('Οι κωδικοί δεν ταιριάζουν.');
      return;
    }

    setLoading(true);
    try {
      await apiClient.post('api/client/set-password/', { uid, token, password });
      setDone(true);
    } catch (err: unknown) {
      const detail =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setError(detail || 'Κάτι πήγε στραβά. Ο σύνδεσμος μπορεί να έχει λήξει.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-100 py-12 px-4 sm:px-6 lg:px-8">
      <div className="max-w-md w-full space-y-8">
        <div className="text-center">
          <div className="mx-auto h-12 w-12 flex items-center justify-center rounded-full bg-brand-100">
            <KeyRound className="h-6 w-6 text-brand-600" />
          </div>
          <h1 className="mt-4 text-3xl font-bold text-gray-900">Ορισμός Κωδικού</h1>
          <h2 className="mt-2 text-lg text-gray-600">
            Δημιουργήστε τον κωδικό σας για την Πύλη Πελάτη
          </h2>
        </div>

        {linkMissing ? (
          <div className="rounded-md bg-red-50 p-4 flex">
            <AlertCircle className="h-5 w-5 text-red-400 shrink-0" />
            <p className="ml-3 text-sm text-red-700">
              Μη έγκυρος σύνδεσμος. Ζητήστε νέο σύνδεσμο από το λογιστικό σας γραφείο.
            </p>
          </div>
        ) : done ? (
          <div className="rounded-md bg-green-50 p-4 flex">
            <CheckCircle className="h-5 w-5 text-green-500 shrink-0" />
            <p className="ml-3 text-sm text-green-700">
              Ο κωδικός ορίστηκε επιτυχώς! Ανακατεύθυνση στη σύνδεση…
            </p>
          </div>
        ) : (
          <form className="mt-8 space-y-6" onSubmit={handleSubmit}>
            {error && (
              <div className="rounded-md bg-red-50 p-4 flex">
                <AlertCircle className="h-5 w-5 text-red-400 shrink-0" />
                <p className="ml-3 text-sm text-red-700">{error}</p>
              </div>
            )}

            <div className="space-y-4">
              <div>
                <label htmlFor="password" className="block text-sm font-medium text-gray-700">
                  Νέος κωδικός
                </label>
                <input
                  id="password"
                  type="password"
                  autoComplete="new-password"
                  required
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm placeholder-gray-400 focus:outline-none focus:ring-brand-500 focus:border-brand-500"
                  placeholder="Τουλάχιστον 8 χαρακτήρες"
                />
              </div>

              <div>
                <label htmlFor="confirm" className="block text-sm font-medium text-gray-700">
                  Επιβεβαίωση κωδικού
                </label>
                <input
                  id="confirm"
                  type="password"
                  autoComplete="new-password"
                  required
                  value={confirm}
                  onChange={(e) => setConfirm(e.target.value)}
                  className="mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm placeholder-gray-400 focus:outline-none focus:ring-brand-500 focus:border-brand-500"
                  placeholder="Επαναλάβετε τον κωδικό"
                />
              </div>
            </div>

            <button
              type="submit"
              disabled={loading}
              className="w-full flex justify-center py-2 px-4 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-brand-600 hover:bg-brand-700 focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-brand-500 disabled:opacity-50"
            >
              {loading ? 'Αποθήκευση…' : 'Ορισμός Κωδικού'}
            </button>
          </form>
        )}
      </div>
    </div>
  );
}
