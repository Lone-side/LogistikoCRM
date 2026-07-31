import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuthStore } from '../stores/authStore';
import { LogIn, AlertCircle } from 'lucide-react';

export default function Login() {
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [rememberMe, setRememberMe] = useState(true);
  const { login, isLoading, error, clearError } = useAuthStore();
  const navigate = useNavigate();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    clearError();

    try {
      await login(username, password, rememberMe);
      navigate('/dashboard');
    } catch {
      // Error is handled in the store
    }
  };

  return (
    <div className="min-h-screen flex bg-slate-100">
      {/* Brand panel (lg+) */}
      <div
        className="hidden lg:flex lg:w-1/2 flex-col justify-between bg-brand-950 text-white p-12 relative overflow-hidden"
        style={{
          backgroundImage:
            'radial-gradient(ellipse at 20% 20%, rgba(43,111,227,0.25), transparent 55%), radial-gradient(ellipse at 80% 90%, rgba(3,105,161,0.3), transparent 50%)',
        }}
      >
        {/* Subtle grid pattern */}
        <div
          className="absolute inset-0 opacity-[0.06] pointer-events-none"
          style={{
            backgroundImage:
              'linear-gradient(rgba(255,255,255,0.6) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,0.6) 1px, transparent 1px)',
            backgroundSize: '48px 48px',
          }}
        />

        <div className="relative flex items-center gap-3">
          <div className="w-11 h-11 bg-gradient-to-br from-brand-600 to-brand-700 rounded-xl flex items-center justify-center shadow-lg shadow-black/30">
            <span className="text-white font-bold">LC</span>
          </div>
          <div>
            <span className="block text-lg font-semibold leading-tight">LogistikoCRM</span>
            <span className="block text-sm text-slate-400 leading-tight">Λογιστικό Γραφείο</span>
          </div>
        </div>

        <div className="relative max-w-md">
          <h2 className="text-3xl font-bold leading-snug">LogistikoCRM</h2>
          <p className="mt-3 text-lg text-slate-300">Σύνδεση στο λογαριασμό σας</p>
        </div>

        <div className="relative text-xs text-slate-500">LogistikoCRM v1.0</div>
      </div>

      {/* Form panel */}
      <div className="flex-1 flex items-center justify-center py-12 px-4 sm:px-6 lg:px-8">
        <div className="max-w-md w-full">
          {/* Mobile brand header */}
          <div className="lg:hidden mb-8 text-center">
            <div className="mx-auto w-12 h-12 bg-gradient-to-br from-brand-600 to-brand-700 rounded-xl flex items-center justify-center shadow-md">
              <span className="text-white font-bold">LC</span>
            </div>
            <h1 className="mt-4 text-3xl font-bold text-slate-900">LogistikoCRM</h1>
          </div>

          <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-6 sm:p-8">
            <div className="hidden lg:block mb-6">
              <h1 className="text-2xl font-bold text-slate-900">LogistikoCRM</h1>
            </div>
            <h2 className="text-lg text-slate-600 mb-6 lg:mt-[-0.5rem]">
              Σύνδεση στο λογαριασμό σας
            </h2>

            <form className="space-y-6" onSubmit={handleSubmit}>
              {error && (
                <div className="rounded-lg bg-danger-50 border border-danger-100 p-4">
                  <div className="flex">
                    <AlertCircle className="h-5 w-5 text-danger-600" />
                    <div className="ml-3">
                      <p className="text-sm text-danger-700">{error}</p>
                    </div>
                  </div>
                </div>
              )}

              <div className="space-y-4">
                <div>
                  <label htmlFor="username" className="block text-sm font-medium text-slate-700">
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
                    className="mt-1 block w-full px-3 py-2 border border-slate-300 rounded-lg shadow-sm placeholder-slate-400 transition-colors duration-150 focus:outline-none focus:ring-2 focus:ring-brand-500/40 focus:border-brand-500"
                    placeholder="Εισάγετε το όνομα χρήστη"
                  />
                </div>

                <div>
                  <label htmlFor="password" className="block text-sm font-medium text-slate-700">
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
                    className="mt-1 block w-full px-3 py-2 border border-slate-300 rounded-lg shadow-sm placeholder-slate-400 transition-colors duration-150 focus:outline-none focus:ring-2 focus:ring-brand-500/40 focus:border-brand-500"
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
                    className="h-4 w-4 text-brand-600 focus:ring-brand-500 border-slate-300 rounded cursor-pointer"
                  />
                  <label htmlFor="remember-me" className="ml-2 block text-sm text-slate-700 cursor-pointer">
                    Να με θυμάσαι
                  </label>
                </div>
              </div>

              <div>
                <button
                  type="submit"
                  disabled={isLoading}
                  className="group relative w-full flex justify-center py-2.5 px-4 border border-transparent text-sm font-medium rounded-lg text-white bg-brand-600 hover:bg-brand-700 transition-colors duration-150 cursor-pointer focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-brand-500 disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  <span className="absolute left-0 inset-y-0 flex items-center pl-3">
                    <LogIn className="h-5 w-5 text-brand-300 group-hover:text-brand-200 transition-colors" />
                  </span>
                  {isLoading ? 'Σύνδεση...' : 'Σύνδεση'}
                </button>
              </div>
            </form>
          </div>
        </div>
      </div>
    </div>
  );
}
