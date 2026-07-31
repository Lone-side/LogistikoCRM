import { useCallback, useEffect, useState } from 'react';
import {
  AlertCircle,
  CheckCircle,
  RefreshCw,
  Send,
  XCircle,
} from 'lucide-react';
import { mydataApi, type MyDataInvoice } from '../api/client';

type SentFilter = 'all' | 'unsent' | 'sent';

function formatCurrency(amount: string | number): string {
  return new Intl.NumberFormat('el-GR', {
    style: 'currency',
    currency: 'EUR',
  }).format(Number(amount));
}

function formatDate(dateStr: string): string {
  return new Intl.DateTimeFormat('el-GR', { dateStyle: 'short' }).format(new Date(dateStr));
}

export default function MyDataInvoices() {
  const [invoices, setInvoices] = useState<MyDataInvoice[]>([]);
  const [loading, setLoading] = useState(false);
  const [busyId, setBusyId] = useState<number | null>(null);
  const [sentFilter, setSentFilter] = useState<SentFilter>('unsent');
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const params: Parameters<typeof mydataApi.invoices.getAll>[0] = {
        direction: 'outgoing',
      };
      if (sentFilter !== 'all') params.mydata_sent = sentFilter === 'sent';
      const data = await mydataApi.invoices.getAll(params);
      setInvoices(Array.isArray(data) ? data : data.results);
    } catch {
      setError('Αποτυχία φόρτωσης τιμολογίων');
    } finally {
      setLoading(false);
    }
  }, [sentFilter]);

  useEffect(() => {
    load();
  }, [load]);

  const handleSend = async (invoice: MyDataInvoice) => {
    if (!window.confirm(
      `Αποστολή του ${invoice.series}/${invoice.number} στο myDATA;\n` +
      'Η ενέργεια δηλώνει το παραστατικό στην ΑΑΔΕ.'
    )) return;

    setBusyId(invoice.id);
    setError(null);
    setSuccess(null);
    try {
      const result = await mydataApi.invoices.send(invoice.id);
      setSuccess(`✅ ${invoice.series}/${invoice.number} εστάλη — MARK ${result.mark}`);
      await load();
    } catch (e: unknown) {
      const detail = (e as { response?: { data?: { error?: string } } })?.response?.data?.error;
      setError(detail || 'Αποτυχία αποστολής στο myDATA');
    } finally {
      setBusyId(null);
    }
  };

  const handleCancel = async (invoice: MyDataInvoice) => {
    if (!window.confirm(
      `Ακύρωση του ${invoice.series}/${invoice.number} (MARK ${invoice.mydata_mark}) στο myDATA;`
    )) return;

    setBusyId(invoice.id);
    setError(null);
    setSuccess(null);
    try {
      const result = await mydataApi.invoices.cancel(invoice.id);
      setSuccess(
        `✅ ${invoice.series}/${invoice.number} ακυρώθηκε — cancellationMark ${result.cancellation_mark}`
      );
      await load();
    } catch (e: unknown) {
      const detail = (e as { response?: { data?: { error?: string } } })?.response?.data?.error;
      setError(detail || 'Αποτυχία ακύρωσης στο myDATA');
    } finally {
      setBusyId(null);
    }
  };

  return (
    <div className="space-y-4">
      {/* Filters */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-4 flex items-center justify-between flex-wrap gap-3">
        <div className="flex gap-2">
          {([
            ['unsent', 'Προς αποστολή'],
            ['sent', 'Απεσταλμένα'],
            ['all', 'Όλα'],
          ] as [SentFilter, string][]).map(([value, label]) => (
            <button
              key={value}
              onClick={() => setSentFilter(value)}
              className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
                sentFilter === value
                  ? 'bg-brand-100 text-brand-700'
                  : 'text-slate-600 hover:bg-slate-100'
              }`}
            >
              {label}
            </button>
          ))}
        </div>
        <button
          onClick={load}
          className="flex items-center gap-2 px-3 py-1.5 rounded-lg border border-slate-300 text-sm hover:bg-slate-50 transition-colors duration-150 cursor-pointer"
        >
          <RefreshCw size={16} className={loading ? 'animate-spin' : ''} />
          Ανανέωση
        </button>
      </div>

      {/* Messages */}
      {error && (
        <div className="bg-danger-50 border border-danger-100 rounded-lg p-4 flex items-center gap-3">
          <AlertCircle size={20} className="text-danger-600 flex-shrink-0" />
          <p className="text-danger-700 text-sm">{error}</p>
        </div>
      )}
      {success && (
        <div className="bg-success-50 border border-success-100 rounded-lg p-4 flex items-center gap-3">
          <CheckCircle size={20} className="text-success-600 flex-shrink-0" />
          <p className="text-success-700 text-sm">{success}</p>
        </div>
      )}

      {/* Table */}
      <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="bg-slate-50 border-b border-slate-200 text-left text-slate-500">
              <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wide text-slate-500">Παραστατικό</th>
              <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wide text-slate-500">Ημ/νία</th>
              <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wide text-slate-500">Πελάτης</th>
              <th className="px-4 py-3 text-xs font-medium uppercase tracking-wide text-slate-500 text-right">Καθαρή</th>
              <th className="px-4 py-3 text-xs font-medium uppercase tracking-wide text-slate-500 text-right">ΦΠΑ</th>
              <th className="px-4 py-3 text-xs font-medium uppercase tracking-wide text-slate-500 text-right">Σύνολο</th>
              <th className="px-4 py-3 text-left text-xs font-medium uppercase tracking-wide text-slate-500">myDATA</th>
              <th className="px-4 py-3 text-xs font-medium uppercase tracking-wide text-slate-500 text-right">Ενέργειες</th>
            </tr>
          </thead>
          <tbody>
            {loading && invoices.length === 0 ? (
              <tr>
                <td colSpan={8} className="px-4 py-10 text-center text-slate-400">
                  <RefreshCw size={22} className="mx-auto mb-2 animate-spin" />
                  Φόρτωση...
                </td>
              </tr>
            ) : invoices.length === 0 ? (
              <tr>
                <td colSpan={8} className="px-4 py-10 text-center text-slate-400">
                  Δεν βρέθηκαν τιμολόγια
                  {sentFilter === 'unsent' && ' προς αποστολή'}
                </td>
              </tr>
            ) : (
              invoices.map((inv) => (
                <tr key={inv.id} className="border-b border-slate-100 hover:bg-slate-50">
                  <td className="px-4 py-3">
                    <span className="font-medium">{inv.series}/{inv.number}</span>
                    <span className="block text-xs text-slate-400">{inv.invoice_type_display}</span>
                  </td>
                  <td className="px-4 py-3 whitespace-nowrap">{formatDate(inv.issue_date)}</td>
                  <td className="px-4 py-3">
                    {inv.counterpart_name}
                    <span className="block text-xs text-slate-400">ΑΦΜ {inv.counterpart_vat}</span>
                  </td>
                  <td className="px-4 py-3 text-right whitespace-nowrap">{formatCurrency(inv.total_net)}</td>
                  <td className="px-4 py-3 text-right whitespace-nowrap">{formatCurrency(inv.total_vat)}</td>
                  <td className="px-4 py-3 text-right font-medium whitespace-nowrap">{formatCurrency(inv.total_gross)}</td>
                  <td className="px-4 py-3">
                    {inv.mydata_cancelled ? (
                      <span
                        className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-slate-100 text-slate-600 text-xs"
                        title={inv.mydata_cancellation_mark ? `cancellationMark ${inv.mydata_cancellation_mark}` : undefined}
                      >
                        <XCircle size={12} /> Ακυρωμένο
                      </span>
                    ) : inv.mydata_sent ? (
                      <span
                        className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-success-100 text-success-700 text-xs"
                        title={inv.mydata_mark ? `MARK ${inv.mydata_mark}` : undefined}
                      >
                        <CheckCircle size={12} /> Εστάλη
                      </span>
                    ) : (
                      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-warning-100 text-warning-700 text-xs">
                        Εκκρεμεί
                      </span>
                    )}
                  </td>
                  <td className="px-4 py-3 text-right">
                    {inv.mydata_cancelled ? (
                      <span className="text-xs text-slate-400">—</span>
                    ) : inv.mydata_sent ? (
                      <button
                        onClick={() => handleCancel(inv)}
                        disabled={busyId === inv.id}
                        className="inline-flex items-center gap-1 px-3 py-1.5 rounded-lg text-xs font-medium text-danger-600 border border-danger-100 hover:bg-danger-50 disabled:opacity-50 transition-colors cursor-pointer"
                      >
                        <XCircle size={14} />
                        Ακύρωση
                      </button>
                    ) : (
                      <button
                        onClick={() => handleSend(inv)}
                        disabled={busyId === inv.id}
                        className="inline-flex items-center gap-1 px-3 py-1.5 rounded-lg text-xs font-medium text-white bg-brand-600 hover:bg-brand-700 disabled:opacity-50 transition-colors cursor-pointer"
                      >
                        {busyId === inv.id
                          ? <RefreshCw size={14} className="animate-spin" />
                          : <Send size={14} />}
                        Αποστολή
                      </button>
                    )}
                  </td>
                </tr>
              ))
            )}
          </tbody>
        </table>
      </div>

      <p className="text-xs text-slate-400">
        Η αποστολή δηλώνει το παραστατικό στην ΑΑΔΕ με τα στοιχεία του γραφείου
        (ρύθμιση MYDATA_ISSUER_VAT). Σε περιβάλλον δοκιμών (sandbox) δεν έχει
        φορολογική ισχύ.
      </p>
    </div>
  );
}
