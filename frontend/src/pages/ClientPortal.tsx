import { useEffect, useRef, useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { portalApi } from '../api/client';
import { useAuthStore } from '../stores/authStore';
import {
  OBLIGATION_STATUS_LABELS,
  OBLIGATION_STATUS_COLORS,
  MONTH_NAMES,
} from '../constants';

type Tab = 'overview' | 'obligations' | 'vat' | 'documents';

interface VatPeriod {
  id: number;
  year: number;
  period: number;
  period_type: string;
  vat_output: string;
  vat_input: string;
  vat_difference: string;
  final_result: string;
  is_locked: boolean;
}

interface VatRecord {
  id: number;
  mark: number;
  issue_date: string;
  kind: 'output' | 'input';
  inv_type: string;
  net_value: string;
  vat_amount: string;
}

interface VatData {
  summary: {
    output: { net: string; vat: string };
    input: { net: string; vat: string };
  };
  periods: VatPeriod[];
  records: VatRecord[];
  records_truncated: boolean;
}

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

  const { data: obligationsData, isLoading: oblLoading, isError: oblError } = useQuery({
    queryKey: ['portal', 'obligations'],
    queryFn: portalApi.getObligations,
  });

  const { data: documentsData, isLoading: docLoading, isError: docError } = useQuery({
    queryKey: ['portal', 'documents'],
    queryFn: portalApi.getDocuments,
  });

  // VAT year filter. undefined = όλα τα έτη (default — αμετάβλητη συμπεριφορά).
  const [vatYear, setVatYear] = useState<number | undefined>(undefined);

  const { data: vatData, isLoading: vatLoading, isError: vatError } = useQuery<VatData>({
    queryKey: ['portal', 'vat', vatYear ?? 'all'],
    queryFn: () => portalApi.getVat(vatYear),
  });

  // Σταθερή λίστα ετών: αντλείται από το ΑΦΙΛΤΡΑΡΙΣΤΟ σύνολο περιόδων, ώστε να
  // μη "χάνονται" επιλογές όταν φιλτράρουμε σε ένα έτος.
  const { data: vatAllYears } = useQuery<VatData>({
    queryKey: ['portal', 'vat', 'all'],
    queryFn: () => portalApi.getVat(undefined),
  });
  const availableYears: number[] = Array.from(
    new Set((vatAllYears?.periods ?? []).map((p) => p.year)),
  ).sort((a, b) => b - a);

  const queryClient = useQueryClient();
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState('');
  const [uploadSuccess, setUploadSuccess] = useState('');
  const [uploadCategory, setUploadCategory] = useState('general');

  const handleUpload = async (file: File) => {
    setUploadError('');
    setUploadSuccess('');
    setUploading(true);
    try {
      await portalApi.uploadDocument(file, uploadCategory);
      setUploadSuccess(`Το αρχείο "${file.name}" ανέβηκε επιτυχώς.`);
      queryClient.invalidateQueries({ queryKey: ['portal', 'documents'] });
    } catch (err: unknown) {
      const detail =
        (err as { response?: { data?: { detail?: string } } })?.response?.data?.detail;
      setUploadError(detail || 'Σφάλμα κατά το ανέβασμα.');
    } finally {
      setUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
  };

  // Client self-sync ΦΠΑ από myDATA (τρέχων μήνας). Το backend επιβάλλει
  // throttle + locked-period guard· εδώ μόνο εμφανίζουμε το αποτέλεσμα.
  const [syncing, setSyncing] = useState(false);
  const [syncMsg, setSyncMsg] = useState<
    { type: 'success' | 'warning' | 'error'; text: string } | null
  >(null);

  const handleSyncVat = async () => {
    setSyncing(true);
    setSyncMsg(null);
    try {
      const res = await portalApi.syncVat();
      if (res?.skipped) {
        setSyncMsg({
          type: 'warning',
          text: res.message ||
            'Ο συγχρονισμός παραλείφθηκε: η περίοδος είναι κλειδωμένη.',
        });
      } else {
        setSyncMsg({ type: 'success', text: 'Ο συγχρονισμός ολοκληρώθηκε.' });
      }
      queryClient.invalidateQueries({ queryKey: ['portal', 'vat'] });
    } catch (err: unknown) {
      const resp = (err as {
        response?: { status?: number; data?: { detail?: string } };
      })?.response;
      const text =
        resp?.status === 429
          ? 'Πολλές προσπάθειες συγχρονισμού. Δοκιμάστε αργότερα.'
          : resp?.data?.detail || 'Σφάλμα συγχρονισμού.';
      setSyncMsg({ type: 'error', text });
    } finally {
      setSyncing(false);
    }
  };

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
        {/* Tabs — horizontally scrollable on narrow screens */}
        <div
          role="tablist"
          aria-label="Ενότητες πύλης"
          className="max-w-5xl mx-auto px-4 flex gap-1 overflow-x-auto"
        >
          {([
            ['overview', 'Επισκόπηση'],
            ['obligations', 'Υποχρεώσεις'],
            ['vat', 'ΦΠΑ'],
            ['documents', 'Έγγραφα'],
          ] as [Tab, string][]).map(([key, label]) => (
            <button
              key={key}
              role="tab"
              aria-selected={tab === key}
              onClick={() => setTab(key)}
              className={`px-4 py-2 text-sm font-medium border-b-2 -mb-px whitespace-nowrap ${
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
          oblError ? (
            <div className="rounded-xl bg-red-50 border border-red-200 p-5 text-sm text-red-700">
              Σφάλμα φόρτωσης δεδομένων. Δοκιμάστε ξανά αργότερα.
            </div>
          ) : oblLoading ? (
            <p className="text-gray-500">Φόρτωση…</p>
          ) : (
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
          )
        )}

        {tab === 'obligations' && (
          <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
            {oblError ? (
              <p className="p-6 text-red-700">Σφάλμα φόρτωσης υποχρεώσεων. Δοκιμάστε ξανά.</p>
            ) : oblLoading ? (
              <p className="p-6 text-gray-500">Φόρτωση…</p>
            ) : obligations.length === 0 ? (
              <p className="p-6 text-gray-500">Δεν υπάρχουν υποχρεώσεις.</p>
            ) : (
              <div className="overflow-x-auto"><table className="w-full text-sm min-w-[480px]">
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
              </table></div>
            )}
          </div>
        )}

        {tab === 'vat' && (
          <div className="space-y-4">
            {/* Φίλτρο έτους + κουμπί self-sync. */}
            <div className="flex items-center justify-between gap-2 flex-wrap">
              <div className="flex items-center gap-2">
                <label htmlFor="vat-year" className="text-sm text-gray-600">
                  Έτος
                </label>
                <select
                  id="vat-year"
                  aria-label="Έτος"
                  value={vatYear ?? ''}
                  onChange={(e) =>
                    setVatYear(e.target.value ? Number(e.target.value) : undefined)
                  }
                  className="text-sm border border-gray-300 rounded-md px-2 py-1.5"
                >
                  <option value="">Όλα τα έτη</option>
                  {availableYears.map((y) => (
                    <option key={y} value={y}>{y}</option>
                  ))}
                </select>
              </div>
              <button
                type="button"
                onClick={handleSyncVat}
                disabled={syncing}
                className="text-sm bg-blue-600 text-white rounded-md px-3 py-1.5 hover:bg-blue-700 disabled:opacity-60"
              >
                {syncing ? 'Συγχρονισμός…' : 'Συγχρονισμός από myDATA'}
              </button>
            </div>

            {syncMsg && (
              <div
                role="status"
                className={
                  syncMsg.type === 'success'
                    ? 'rounded-md bg-green-50 border border-green-200 p-3 text-sm text-green-700'
                    : syncMsg.type === 'warning'
                    ? 'rounded-md bg-amber-50 border border-amber-200 p-3 text-sm text-amber-800'
                    : 'rounded-md bg-red-50 border border-red-200 p-3 text-sm text-red-700'
                }
              >
                {syncMsg.text}
              </div>
            )}

            {vatError ? (
              <div className="rounded-xl bg-red-50 border border-red-200 p-5 text-sm text-red-700">
                Σφάλμα φόρτωσης δεδομένων ΦΠΑ.
              </div>
            ) : vatLoading || !vatData ? (
              <p className="text-gray-500">Φόρτωση…</p>
            ) : (
              <>
                <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                  <div className="bg-white rounded-xl border border-gray-200 p-5">
                    <p className="text-sm text-gray-500">Εκροές (Έσοδα)</p>
                    <p className="text-xs text-gray-500 mt-2">Καθαρή Αξία</p>
                    <p className="text-2xl font-bold text-gray-900">€{vatData.summary.output.net}</p>
                    <p className="text-xs text-gray-500 mt-2">ΦΠΑ</p>
                    <p className="text-lg font-semibold text-blue-600">€{vatData.summary.output.vat}</p>
                  </div>
                  <div className="bg-white rounded-xl border border-gray-200 p-5">
                    <p className="text-sm text-gray-500">Εισροές (Έξοδα)</p>
                    <p className="text-xs text-gray-500 mt-2">Καθαρή Αξία</p>
                    <p className="text-2xl font-bold text-gray-900">€{vatData.summary.input.net}</p>
                    <p className="text-xs text-gray-500 mt-2">ΦΠΑ</p>
                    <p className="text-lg font-semibold text-blue-600">€{vatData.summary.input.vat}</p>
                  </div>
                </div>

                <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
                  <div className="px-4 py-3 border-b border-gray-100 font-medium text-gray-900">
                    Περίοδοι ΦΠΑ
                  </div>
                  {vatData.periods.length === 0 ? (
                    <p className="p-6 text-gray-500">Δεν υπάρχουν υπολογισμένες περίοδοι.</p>
                  ) : (
                    <div className="overflow-x-auto"><table className="w-full text-sm min-w-[480px]">
                      <thead className="bg-gray-50 text-gray-600">
                        <tr>
                          <th className="text-left px-4 py-3 font-medium">Περίοδος</th>
                          <th className="text-right px-4 py-3 font-medium">ΦΠΑ Εκροών</th>
                          <th className="text-right px-4 py-3 font-medium">ΦΠΑ Εισροών</th>
                          <th className="text-right px-4 py-3 font-medium">Διαφορά</th>
                          <th className="text-right px-4 py-3 font-medium">Τελικό</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-gray-100">
                        {vatData.periods.map((p) => (
                          <tr key={p.id} className="hover:bg-gray-50">
                            <td className="px-4 py-3 text-gray-900">
                              {MONTH_NAMES[p.period - 1] || p.period} {p.year}
                              {p.is_locked && (
                                <span className="ml-2 text-xs px-2 py-0.5 bg-gray-200 rounded text-gray-700">
                                  κλειδωμένο
                                </span>
                              )}
                            </td>
                            <td className="px-4 py-3 text-right text-gray-700">€{p.vat_output}</td>
                            <td className="px-4 py-3 text-right text-gray-700">€{p.vat_input}</td>
                            <td className="px-4 py-3 text-right text-gray-700">€{p.vat_difference}</td>
                            <td className="px-4 py-3 text-right font-semibold text-gray-900">€{p.final_result}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table></div>
                  )}
                </div>

                <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
                  <div className="px-4 py-3 border-b border-gray-100 font-medium text-gray-900">
                    Πρόσφατα παραστατικά{vatData.records_truncated && ' (πρώτα 50)'}
                  </div>
                  {vatData.records.length === 0 ? (
                    <p className="p-6 text-gray-500">Δεν υπάρχουν παραστατικά.</p>
                  ) : (
                    <div className="overflow-x-auto"><table className="w-full text-sm min-w-[480px]">
                      <thead className="bg-gray-50 text-gray-600">
                        <tr>
                          <th className="text-left px-4 py-3 font-medium">Ημερομηνία</th>
                          <th className="text-left px-4 py-3 font-medium">Τύπος</th>
                          <th className="text-left px-4 py-3 font-medium">MARK</th>
                          <th className="text-right px-4 py-3 font-medium">Καθαρή</th>
                          <th className="text-right px-4 py-3 font-medium">ΦΠΑ</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-gray-100">
                        {vatData.records.map((r) => (
                          <tr key={r.id} className="hover:bg-gray-50">
                            <td className="px-4 py-3 text-gray-700">{r.issue_date}</td>
                            <td className="px-4 py-3">
                              <span className={`inline-flex px-2 py-1 text-xs font-medium rounded-full ${
                                r.kind === 'output' ? 'bg-green-50 text-green-700' : 'bg-amber-50 text-amber-700'
                              }`}>
                                {r.kind === 'output' ? 'Εκροή' : 'Εισροή'}
                              </span>
                            </td>
                            <td className="px-4 py-3 text-gray-600 font-mono text-xs">{r.mark}</td>
                            <td className="px-4 py-3 text-right text-gray-700">€{r.net_value}</td>
                            <td className="px-4 py-3 text-right text-gray-900 font-medium">€{r.vat_amount}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table></div>
                  )}
                </div>
              </>
            )}
          </div>
        )}

        {tab === 'documents' && (
          <div className="space-y-4">
            {/* Upload box */}
            <div className="bg-white rounded-xl border border-gray-200 p-5">
              <div className="flex items-center justify-between flex-wrap gap-3">
                <div>
                  <p className="font-medium text-gray-900">Ανέβασμα εγγράφου</p>
                  <p className="text-sm text-gray-500">PDF, Word, Excel, εικόνες — έως 10MB</p>
                </div>
                <div className="flex items-center gap-3">
                  <select
                    value={uploadCategory}
                    onChange={(e) => setUploadCategory(e.target.value)}
                    className="text-sm border border-gray-300 rounded-md px-2 py-1.5"
                    disabled={uploading}
                  >
                    <option value="general">Γενικά</option>
                    <option value="invoices">Τιμολόγια</option>
                    <option value="contracts">Συμβάσεις</option>
                    <option value="tax">Φορολογικά</option>
                    <option value="vat">ΦΠΑ</option>
                    <option value="myf">ΜΥΦ</option>
                    <option value="payroll">Μισθοδοσία</option>
                  </select>
                  <input
                    ref={fileInputRef}
                    type="file"
                    className="hidden"
                    onChange={(e) => {
                      const f = e.target.files?.[0];
                      if (f) handleUpload(f);
                    }}
                  />
                  <button
                    onClick={() => fileInputRef.current?.click()}
                    disabled={uploading}
                    className="px-4 py-2 bg-blue-600 text-white text-sm font-medium rounded-md hover:bg-blue-700 disabled:opacity-50"
                  >
                    {uploading ? 'Ανέβασμα…' : 'Επιλογή αρχείου'}
                  </button>
                </div>
              </div>
              {uploadError && (
                <p className="mt-3 text-sm text-red-700 bg-red-50 border border-red-200 rounded-md p-2">
                  {uploadError}
                </p>
              )}
              {uploadSuccess && (
                <p className="mt-3 text-sm text-green-700 bg-green-50 border border-green-200 rounded-md p-2">
                  {uploadSuccess}
                </p>
              )}
            </div>

          <div className="bg-white rounded-xl border border-gray-200 overflow-hidden">
            {docError ? (
              <p className="p-6 text-red-700">Σφάλμα φόρτωσης εγγράφων. Δοκιμάστε ξανά.</p>
            ) : docLoading ? (
              <p className="p-6 text-gray-500">Φόρτωση…</p>
            ) : documents.length === 0 ? (
              <p className="p-6 text-gray-500">Δεν υπάρχουν έγγραφα.</p>
            ) : (
              <div className="overflow-x-auto"><table className="w-full text-sm min-w-[480px]">
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
              </table></div>
            )}
          </div>
          </div>
        )}
      </main>
    </div>
  );
}
