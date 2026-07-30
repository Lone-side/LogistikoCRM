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
      <div className="bg-white rounded-lg border border-gray-200 p-4 flex items-center justify-between flex-wrap gap-3">
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
                  ? 'bg-blue-100 text-blue-700'
                  : 'text-gray-600 hover:bg-gray-100'
              }`}
            >
              {label}
            </button>
          ))}
        </div>
        <button
          onClick={load}
          className="flex items-center gap-2 px-3 py-1.5 rounded-lg border border-gray-300 text-sm hover:bg-gray-50 transition-colors"
        >
          <RefreshCw size={16} className={loading ? 'animate-spin' : ''} />
          Ανανέωση
        </button>
      </div>

      {/* Messages */}
      {error && (
        <div className="bg-red-50 border border-red-200 rounded-lg p-4 flex items-center gap-3">
          <AlertCircle size={20} className="text-red-500 flex-shrink-0" />
          <p className="text-red-700 text-sm">{error}</p>
        </div>
      )}
      {success && (
        <div className="bg-green-50 border border-green-200 rounded-lg p-4 flex items-center gap-3">
          <CheckCircle size={20} className="text-green-500 flex-shrink-0" />
          <p className="text-green-700 text-sm">{success}</p>
        </div>
      )}

      {/* Table */}
      <div className="bg-white rounded-lg border border-gray-200 overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-gray-200 text-left text-gray-500">
              <th className="px-4 py-3 font-medium">Παραστατικό</th>
              <th className="px-4 py-3 font-medium">Ημ/νία</th>
              <th className="px-4 py-3 font-medium">Πελάτης</th>
              <th className="px-4 py-3 font-medium text-right">Καθαρή</th>
              <th className="px-4 py-3 font-medium text-right">ΦΠΑ</th>
              <th className="px-4 py-3 font-medium text-right">Σύνολο</th>
              <th className="px-4 py-3 font-medium">myDATA</th>
              <th className="px-4 py-3 font-medium text-right">Ενέργειες</th>
            </tr>
          </thead>
          <tbody>
            {loading && invoices.length === 0 ? (
              <tr>
                <td colSpan={8} className="px-4 py-10 text-center text-gray-400">
                  <RefreshCw size={22} className="mx-auto mb-2 animate-spin" />
                  Φόρτωση...
                </td>
              </tr>
            ) : invoices.length === 0 ? (
              <tr>
                <td colSpan={8} className="px-4 py-10 text-center text-gray-400">
                  Δεν βρέθηκαν τιμολόγια
                  {sentFilter === 'unsent' && ' προς αποστολή'}
                </td>
              </tr>
            ) : (
              invoices.map((inv) => (
                <tr key={inv.id} className="border-b border-gray-100 hover:bg-gray-50">
                  <td className="px-4 py-3">
                    <span className="font-medium">{inv.series}/{inv.number}</span>
                    <span className="block text-xs text-gray-400">{inv.invoice_type_display}</span>
                  </td>
                  <td className="px-4 py-3 whitespace-nowrap">{formatDate(inv.issue_date)}</td>
                  <td className="px-4 py-3">
                    {inv.counterpart_name}
                    <span className="block text-xs text-gray-400">ΑΦΜ {inv.counterpart_vat}</span>
                  </td>
                  <td className="px-4 py-3 text-right whitespace-nowrap">{formatCurrency(inv.total_net)}</td>
                  <td className="px-4 py-3 text-right whitespace-nowrap">{formatCurrency(inv.total_vat)}</td>
                  <td className="px-4 py-3 text-right font-medium whitespace-nowrap">{formatCurrency(inv.total_gross)}</td>
                  <td className="px-4 py-3">
                    {inv.mydata_cancelled ? (
                      <span
                        className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-gray-100 text-gray-600 text-xs"
                        title={inv.mydata_cancellation_mark ? `cancellationMark ${inv.mydata_cancellation_mark}` : undefined}
                      >
                        <XCircle size={12} /> Ακυρωμένο
                      </span>
                    ) : inv.mydata_sent ? (
                      <span
                        className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-green-100 text-green-700 text-xs"
                        title={inv.mydata_mark ? `MARK ${inv.mydata_mark}` : undefined}
                      >
                        <CheckCircle size={12} /> Εστάλη
                      </span>
                    ) : (
                      <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-yellow-100 text-yellow-700 text-xs">
                        Εκκρεμεί
                      </span>
                    )}
                  </td>
                  <td className="px-4 py-3 text-right">
                    {inv.mydata_cancelled ? (
                      <span className="text-xs text-gray-400">—</span>
                    ) : inv.mydata_sent ? (
                      <button
                        onClick={() => handleCancel(inv)}
                        disabled={busyId === inv.id}
                        className="inline-flex items-center gap-1 px-3 py-1.5 rounded-lg text-xs font-medium text-red-600 border border-red-200 hover:bg-red-50 disabled:opacity-50 transition-colors"
                      >
                        <XCircle size={14} />
                        Ακύρωση
                      </button>
                    ) : (
                      <button
                        onClick={() => handleSend(inv)}
                        disabled={busyId === inv.id}
                        className="inline-flex items-center gap-1 px-3 py-1.5 rounded-lg text-xs font-medium text-white bg-blue-600 hover:bg-blue-700 disabled:opacity-50 transition-colors"
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

      <p className="text-xs text-gray-400">
        Η αποστολή δηλώνει το παραστατικό στην ΑΑΔΕ με τα στοιχεία του γραφείου
        (ρύθμιση MYDATA_ISSUER_VAT). Σε περιβάλλον δοκιμών (sandbox) δεν έχει
        φορολογική ισχύ.
      </p>
    </div>
  );
}
