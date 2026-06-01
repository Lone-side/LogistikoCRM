import { useEffect, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { portalApi } from '../api/client';
import { useAuthStore } from '../stores/authStore';
import {
  OBLIGATION_STATUS_LABELS,
  OBLIGATION_STATUS_COLORS,
  MONTH_NAMES,
} from '../constants';

type Tab = 'overview' | 'obligations' | 'documents';

interface PortalObligation {
  id: number;
  obligation_type: string | null;
  obligation_type_code: string | null;
  year: number;
  month: number;
  deadline: string;
  status: string;
  deadline_status: string;
  completed_date: string | null;
}

interface PortalDocument {
  id: number;
  filename: string;
  file_type: string;
  document_category: string;
  uploaded_at: string;
  obligation: string | null;
  download_url: string | null;
}

function StatusBadge({ status }: { status: string }) {
  const color = OBLIGATION_STATUS_COLORS[status] || 'bg-gray-100 text-gray-700';
  const label = OBLIGATION_STATUS_LABELS[status] || status;
  return (
    <span className={`inline-flex px-2 py-1 text-xs font-medium rounded-full ${color}`}>
      {label}
    </span>
  );
}

export default function ClientPortal() {
  const [tab, setTab] = useState<Tab>('overview');
  const user = useAuthStore((s) => s.user);
  const logout = useAuthStore((s) => s.logout);

  const { data: profile } = useQuery({
    queryKey: ['portal', 'profile'],
    queryFn: portalApi.getProfile,
  });

  const { data: obligationsData, isLoading: oblLoading } = useQuery({
    queryKey: ['portal', 'obligations'],
    queryFn: portalApi.getObligations,
  });

  const { data: documentsData, isLoading: docLoading } = useQuery({
    queryKey: ['portal', 'documents'],
    queryFn: portalApi.getDocuments,
  });

  const obligations: PortalObligation[] = obligationsData?.results || [];
  const documents: PortalDocument[] = documentsData?.results || [];

  const pending = obligations.filter((o) => o.status === 'pending').length;
  const overdue = obligations.filter((o) => o.deadline_status === 'overdue').length;
  const completed = obligations.filter((o) => o.status === 'completed').length;

  useEffect(() => {
    document.title = 'Πύλη Πελάτη — LogistikoCRM';
  }, []);

  return (
    <div className="min-h-screen bg-gray-50">
      {/* Header */}
      <header className="bg-white border-b border-gray-200">
        <div className="max-w-5xl mx-auto px-4 py-4 flex items-center justify-between">
          <div>
            <h1 className="text-lg font-semibold text-gray-900">
              {profile?.eponimia || user?.client_name || 'Πύλη Πελάτη'}
            </h1>
            <p className="text-sm text-gray-500">ΑΦΜ: {profile?.afm || user?.client_afm || '—'}</p>
          </div>
          <button
            onClick={() => logout()}
            className="text-sm text-gray-600 hover:text-gray-900 px-3 py-2 rounded-lg hover:bg-gray-100"
          >
            Αποσύνδεση
          </button>
        </div>
        {/* Tabs */}
        <div className="max-w-5xl mx-auto px-4 flex gap-1">
          {([
            ['overview', 'Επισκόπηση'],
            ['obligations', 'Υποχρεώσεις'],
            ['documents', 'Έγγραφα'],
          ] as [Tab, string][]).map(([key, label]) => (
            <button
              key={key}
              onClick={() => setTab(key)}
              className={`px-4 py-2 text-sm font-medium border-b-2 -mb-px ${
                tab === key
                  ? 'border-blue-600 text-blue-600'
                  : 'border-transparent text-gray-500 hover:text-gray-700'
              }`}
            >
              {label}
            </button>
          ))}
        </div>
      </header>

      <main className="max-w-5xl mx-auto px-4 py-6">
        {tab === 'overview' && (
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <div className="bg-white rounded-xl border border-gray-200 p-5">
              <p className="text-sm text-gray-500">Εκκρεμείς</p>
              <p className="text-3xl font-bold text-amber-600 mt-1">{pending}</p>
            </div>
            <div className="bg-white rounded-xl border border-gray-200 p-5">
              <p className="text-sm text-gray-500">Εκπρόθεσμες</p>
              <p className="text-3xl font-bold text-red-600 mt-1">{overdue}</p>
            </div>
            <div className="bg-white rounded-xl border border-gray-200 p-5">
              <p className="text-sm text-gray-500">Ολοκληρωμένες</p>
              <p className="text-3xl font-bold text-green-600 mt-1">{completed}</p>
            </div>
          </div>
        )}

        {tab === 'obligations' && (
          <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
            {oblLoading ? (
              <p className="p-6 text-gray-500">Φόρτωση…</p>
            ) : obligations.length === 0 ? (
              <p className="p-6 text-gray-500">Δεν υπάρχουν υποχρεώσεις.</p>
            ) : (
              <table className="w-full text-sm">
                <thead className="bg-gray-50 text-gray-600">
                  <tr>
                    <th className="text-left px-4 py-3 font-medium">Υποχρέωση</th>
                    <th className="text-left px-4 py-3 font-medium">Περίοδος</th>
                    <th className="text-left px-4 py-3 font-medium">Προθεσμία</th>
                    <th className="text-left px-4 py-3 font-medium">Κατάσταση</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {obligations.map((o) => (
                    <tr key={o.id} className="hover:bg-gray-50">
                      <td className="px-4 py-3 text-gray-900">{o.obligation_type || '—'}</td>
                      <td className="px-4 py-3 text-gray-600">
                        {MONTH_NAMES[o.month - 1] || o.month} {o.year}
                      </td>
                      <td className="px-4 py-3 text-gray-600">{o.deadline}</td>
                      <td className="px-4 py-3"><StatusBadge status={o.status} /></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        )}

        {tab === 'documents' && (
          <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
            {docLoading ? (
              <p className="p-6 text-gray-500">Φόρτωση…</p>
            ) : documents.length === 0 ? (
              <p className="p-6 text-gray-500">Δεν υπάρχουν έγγραφα.</p>
            ) : (
              <table className="w-full text-sm">
                <thead className="bg-gray-50 text-gray-600">
                  <tr>
                    <th className="text-left px-4 py-3 font-medium">Αρχείο</th>
                    <th className="text-left px-4 py-3 font-medium">Υποχρέωση</th>
                    <th className="text-left px-4 py-3 font-medium">Ημερομηνία</th>
                    <th className="text-right px-4 py-3 font-medium">Λήψη</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {documents.map((d) => (
                    <tr key={d.id} className="hover:bg-gray-50">
                      <td className="px-4 py-3 text-gray-900">{d.filename}</td>
                      <td className="px-4 py-3 text-gray-600">{d.obligation || '—'}</td>
                      <td className="px-4 py-3 text-gray-600">
                        {d.uploaded_at ? new Date(d.uploaded_at).toLocaleDateString('el-GR') : '—'}
                      </td>
                      <td className="px-4 py-3 text-right">
                        {d.download_url ? (
                          <a
                            href={d.download_url}
                            className="text-blue-600 hover:text-blue-800 font-medium"
                            target="_blank"
                            rel="noreferrer"
                          >
                            Λήψη
                          </a>
                        ) : (
                          <span className="text-gray-400">—</span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        )}
      </main>
    </div>
  );
}
