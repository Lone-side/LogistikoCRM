import { useState, useEffect, useCallback } from 'react';
import {
  FileText,
  TrendingUp,
  TrendingDown,
  Calendar,
  RefreshCw,
  ChevronLeft,
  ChevronRight,
  AlertCircle,
  CheckCircle,
  Users,
  BarChart3,
  Calculator,
  ChevronDown,
} from 'lucide-react';
import { Button, VATPeriodCalculator } from '../components';
import MyDataInvoices from '../components/MyDataInvoices';
import { mydataApi, clientsApi, type ClientVATDetailResponse } from '../api/client';

// Types
interface Client {
  id: number;
  afm: string;
  eponimia: string;
}

// Greek month names
const MONTHS = [
  'Ιανουάριος', 'Φεβρουάριος', 'Μάρτιος', 'Απρίλιος',
  'Μάιος', 'Ιούνιος', 'Ιούλιος', 'Αύγουστος',
  'Σεπτέμβριος', 'Οκτώβριος', 'Νοέμβριος', 'Δεκέμβριος'
];

function formatCurrency(amount: number): string {
  return new Intl.NumberFormat('el-GR', {
    style: 'currency',
    currency: 'EUR',
  }).format(amount);
}

function formatDateTime(dateStr: string | null): string {
  if (!dateStr) return '-';
  return new Intl.DateTimeFormat('el-GR', {
    dateStyle: 'short',
    timeStyle: 'short',
  }).format(new Date(dateStr));
}

// Tab types
type TabType = 'overview' | 'calculator' | 'invoices';

export default function MyData() {
  // Tab state
  const [activeTab, setActiveTab] = useState<TabType>('overview');

  // Client selection
  const [clients, setClients] = useState<Client[]>([]);
  const [selectedClientId, setSelectedClientId] = useState<number | null>(null);
  const [credentialsId, setCredentialsId] = useState<number | null>(null);

  // Period selection
  const now = new Date();
  const [year, setYear] = useState(now.getFullYear());
  const [month, setMonth] = useState(now.getMonth() + 1);

  // Data state
  const [loading, setLoading] = useState(false);
  const [syncing, setSyncing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [clientData, setClientData] = useState<ClientVATDetailResponse | null>(null);

  // Fetch clients on mount
  useEffect(() => {
    const fetchClients = async () => {
      try {
        const response = await clientsApi.getAll({ page_size: 1000 });
        const clientList = response.results || response;
        setClients(clientList);
        // Auto-select first client if available
        if (clientList.length > 0) setSelectedClientId(current => current ?? clientList[0].id);
      } catch (err) {
        console.error('Error fetching clients:', err);
      }
    };
    fetchClients();
  }, []);

  // Find selected client's AFM
  const selectedClient = clients.find(c => c.id === selectedClientId);

  // Fetch VAT data for selected client
  const fetchClientData = useCallback(async () => {
    if (!selectedClient) return;

    setLoading(true);
    setError(null);
    setSuccessMessage(null);

    try {
      // Get client VAT details
      const data = await mydataApi.getClientVAT(selectedClient.afm, year, month);
      setClientData(data);

      // Try to get credentials ID for sync
      try {
        const creds = await mydataApi.credentials.getByClient(selectedClientId!);
        setCredentialsId(creds.id);
      } catch {
        setCredentialsId(null);
      }
    } catch (err) {
      console.error('Error fetching client VAT data:', err);
      setError('Σφάλμα φόρτωσης δεδομένων ΦΠΑ');
      setClientData(null);
    } finally {
      setLoading(false);
    }
  }, [selectedClient, selectedClientId, year, month]);

  // Fetch client VAT data when client or period changes
  useEffect(() => {
    if (selectedClientId && activeTab === 'overview') {
      fetchClientData();
    }
  }, [selectedClientId, activeTab, fetchClientData]);

  // Sync VAT data from myDATA
  const handleSync = async () => {
    if (!credentialsId) {
      setError('Δεν βρέθηκαν credentials για αυτόν τον πελάτη');
      return;
    }

    setSyncing(true);
    setError(null);
    setSuccessMessage(null);

    try {
      await mydataApi.credentials.sync(credentialsId, year, month);
      setSuccessMessage('Ο συγχρονισμός ολοκληρώθηκε επιτυχώς');
      // Refresh data after sync
      await fetchClientData();
    } catch (err: unknown) {
      console.error('Sync error:', err);
      const axiosError = err as { response?: { data?: { error?: string } } };
      setError(axiosError.response?.data?.error || 'Σφάλμα συγχρονισμού');
    } finally {
      setSyncing(false);
    }
  };

  // Navigate months
  const goToPreviousMonth = () => {
    if (month === 1) {
      setMonth(12);
      setYear(year - 1);
    } else {
      setMonth(month - 1);
    }
  };

  const goToNextMonth = () => {
    if (month === 12) {
      setMonth(1);
      setYear(year + 1);
    } else {
      setMonth(month + 1);
    }
  };

  // Calculate VAT result
  const vatResult = clientData?.summary
    ? clientData.summary.income_vat - clientData.summary.expense_vat
    : 0;
  const isPayable = vatResult > 0;

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center gap-3">
        <div className="w-10 h-10 bg-brand-100 rounded-lg flex items-center justify-center">
          <FileText size={20} className="text-brand-600" />
        </div>
        <div>
          <h1 className="text-2xl font-bold text-slate-900">myDATA - Αποτέλεσμα ΦΠΑ</h1>
          <p className="text-slate-500">Παρακολούθηση ΦΠΑ από τα ηλεκτρονικά βιβλία ΑΑΔΕ</p>
        </div>
      </div>

      {/* Tabs */}
      <div className="border-b border-slate-200">
        <nav className="flex gap-4">
          <button
            onClick={() => setActiveTab('overview')}
            className={`flex items-center gap-2 px-4 py-3 border-b-2 font-medium text-sm transition-colors ${
              activeTab === 'overview'
                ? 'border-brand-500 text-brand-600'
                : 'border-transparent text-slate-500 hover:text-slate-700 hover:border-slate-300'
            }`}
          >
            <BarChart3 size={18} />
            Επισκόπηση
          </button>
          <button
            onClick={() => setActiveTab('calculator')}
            className={`flex items-center gap-2 px-4 py-3 border-b-2 font-medium text-sm transition-colors ${
              activeTab === 'calculator'
                ? 'border-brand-500 text-brand-600'
                : 'border-transparent text-slate-500 hover:text-slate-700 hover:border-slate-300'
            }`}
          >
            <Calculator size={18} />
            Υπολογισμός Περιόδου
          </button>
          <button
            onClick={() => setActiveTab('invoices')}
            className={`flex items-center gap-2 px-4 py-3 border-b-2 font-medium text-sm transition-colors ${
              activeTab === 'invoices'
                ? 'border-brand-500 text-brand-600'
                : 'border-transparent text-slate-500 hover:text-slate-700 hover:border-slate-300'
            }`}
          >
            <FileText size={18} />
            Τιμολόγια
          </button>
        </nav>
      </div>

      {/* Tab Content */}
      {activeTab === 'overview' ? (
        <div className="space-y-6">
          {/* Filters Row */}
          <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-4">
            <div className="flex flex-col md:flex-row md:items-center gap-4">
              {/* Client Selector */}
              <div className="flex-1">
                <label className="block text-sm font-medium text-slate-700 mb-1">Πελάτης</label>
                <div className="relative">
                  <select
                    value={selectedClientId || ''}
                    onChange={(e) => setSelectedClientId(e.target.value ? Number(e.target.value) : null)}
                    className="w-full pl-3 pr-10 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-brand-500/30 focus:border-brand-500 appearance-none bg-white"
                  >
                    <option value="">-- Επιλέξτε Πελάτη --</option>
                    {clients.map((client) => (
                      <option key={client.id} value={client.id}>
                        {client.eponimia} ({client.afm})
                      </option>
                    ))}
                  </select>
                  <ChevronDown size={16} className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 pointer-events-none" />
                </div>
              </div>

              {/* Period Selector */}
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">Περίοδος</label>
                <div className="flex items-center gap-2">
                  <button
                    onClick={goToPreviousMonth}
                    className="p-2 rounded-lg border border-slate-300 hover:bg-slate-50 transition-colors duration-150 cursor-pointer"
                  >
                    <ChevronLeft size={18} />
                  </button>
                  <div className="flex items-center gap-2 px-4 py-2 bg-slate-50 rounded-lg min-w-[180px] justify-center">
                    <Calendar size={16} className="text-slate-400" />
                    <span className="font-medium">{MONTHS[month - 1]} {year}</span>
                  </div>
                  <button
                    onClick={goToNextMonth}
                    className="p-2 rounded-lg border border-slate-300 hover:bg-slate-50 transition-colors duration-150 cursor-pointer"
                  >
                    <ChevronRight size={18} />
                  </button>
                </div>
              </div>
            </div>
          </div>

          {/* Loading State */}
          {loading && (
            <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-12 text-center">
              <RefreshCw size={32} className="mx-auto mb-4 text-brand-500 animate-spin" />
              <p className="text-slate-500">Φόρτωση δεδομένων...</p>
            </div>
          )}

          {/* Error Message */}
          {error && (
            <div className="bg-danger-50 border border-danger-100 rounded-lg p-4 flex items-center gap-3">
              <AlertCircle size={20} className="text-danger-600 flex-shrink-0" />
              <p className="text-danger-700">{error}</p>
            </div>
          )}

          {/* Success Message */}
          {successMessage && (
            <div className="bg-success-50 border border-success-100 rounded-lg p-4 flex items-center gap-3">
              <CheckCircle size={20} className="text-success-600 flex-shrink-0" />
              <p className="text-success-700">{successMessage}</p>
            </div>
          )}

          {/* No Client Selected */}
          {!selectedClientId && !loading && (
            <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-12 text-center">
              <Users size={48} className="mx-auto mb-4 text-slate-300" />
              <p className="text-slate-500">Επιλέξτε πελάτη για να δείτε τα στοιχεία ΦΠΑ</p>
            </div>
          )}

          {/* VAT Results */}
          {clientData && !loading && (
            <>
              {/* Main Result Card */}
              <div className={`rounded-xl border-2 p-8 text-center ${
                isPayable
                  ? 'bg-success-50 border-success-100'
                  : 'bg-danger-50 border-danger-100'
              }`}>
                <p className="text-sm text-slate-600 mb-1">ΑΠΟΤΕΛΕΣΜΑ ΦΠΑ</p>
                <p className="text-sm text-slate-500 mb-4">{MONTHS[month - 1].toUpperCase()} {year}</p>

                <p className={`text-5xl font-bold mb-4 ${isPayable ? 'text-success-600' : 'text-danger-600'}`}>
                  {isPayable ? '+' : ''}{formatCurrency(vatResult)}
                </p>

                <div className={`inline-flex items-center gap-2 px-4 py-2 rounded-full ${
                  isPayable
                    ? 'bg-success-100 text-success-700'
                    : 'bg-danger-100 text-danger-700'
                }`}>
                  {isPayable ? <TrendingUp size={18} /> : <TrendingDown size={18} />}
                  <span className="font-medium">
                    {isPayable ? 'ΦΠΑ για Καταβολή' : 'Πιστωτικό Υπόλοιπο'}
                  </span>
                </div>
              </div>

              {/* VAT Breakdown */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                {/* Income VAT */}
                <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-6 text-center">
                  <p className="text-sm text-slate-500 mb-2">ΦΠΑ Εκροών</p>
                  <p className="text-3xl font-bold text-success-600 mb-1">
                    {formatCurrency(clientData.summary.income_vat)}
                  </p>
                  <p className="text-sm text-slate-400">
                    {clientData.summary.income_count} εγγραφές
                  </p>
                </div>

                {/* Expense VAT */}
                <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-6 text-center">
                  <p className="text-sm text-slate-500 mb-2">ΦΠΑ Εισροών</p>
                  <p className="text-3xl font-bold text-danger-600 mb-1">
                    {formatCurrency(clientData.summary.expense_vat)}
                  </p>
                  <p className="text-sm text-slate-400">
                    {clientData.summary.expense_count} εγγραφές
                  </p>
                </div>
              </div>

              {/* Sync Section */}
              <div className="bg-white rounded-xl border border-slate-200 shadow-sm p-4">
                <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
                  <Button
                    onClick={handleSync}
                    disabled={syncing || !credentialsId}
                    className="bg-brand-600 hover:bg-brand-700"
                  >
                    {syncing ? (
                      <>
                        <RefreshCw size={18} className="mr-2 animate-spin" />
                        Συγχρονισμός...
                      </>
                    ) : (
                      <>
                        <RefreshCw size={18} className="mr-2" />
                        Sync από myDATA
                      </>
                    )}
                  </Button>

                  <div className="text-right text-sm text-slate-500">
                    <p>Τελ. ενημέρωση:</p>
                    <p className="font-medium">{formatDateTime(clientData.credentials.last_sync)}</p>
                  </div>
                </div>
              </div>

              {/* Category Breakdown */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                {/* Income by Category */}
                <div className="bg-white rounded-xl border border-slate-200 shadow-sm">
                  <div className="p-4 border-b border-slate-200">
                    <h3 className="font-semibold text-slate-900 flex items-center gap-2">
                      <TrendingUp size={18} className="text-success-600" />
                      ΦΠΑ Εκροών ανά Κατηγορία
                    </h3>
                  </div>
                  <div className="p-4">
                    {clientData.income_by_category && clientData.income_by_category.length > 0 ? (
                      <div className="space-y-3">
                        {clientData.income_by_category.map((cat) => (
                          <div key={cat.vat_category} className="flex items-center justify-between">
                            <div className="flex items-center gap-2">
                              <span className="px-2 py-1 bg-success-100 text-success-700 text-xs font-medium rounded">
                                {cat.vat_rate_display}
                              </span>
                              <span className="text-sm text-slate-600">
                                ({cat.count} εγγρ.)
                              </span>
                            </div>
                            <span className="font-semibold text-success-600">
                              {formatCurrency(cat.vat_amount)}
                            </span>
                          </div>
                        ))}
                      </div>
                    ) : (
                      <p className="text-slate-400 text-center py-4">Δεν υπάρχουν εγγραφές</p>
                    )}
                  </div>
                </div>

                {/* Expense by Category */}
                <div className="bg-white rounded-xl border border-slate-200 shadow-sm">
                  <div className="p-4 border-b border-slate-200">
                    <h3 className="font-semibold text-slate-900 flex items-center gap-2">
                      <TrendingDown size={18} className="text-danger-600" />
                      ΦΠΑ Εισροών ανά Κατηγορία
                    </h3>
                  </div>
                  <div className="p-4">
                    {clientData.expense_by_category && clientData.expense_by_category.length > 0 ? (
                      <div className="space-y-3">
                        {clientData.expense_by_category.map((cat) => (
                          <div key={cat.vat_category} className="flex items-center justify-between">
                            <div className="flex items-center gap-2">
                              <span className="px-2 py-1 bg-danger-100 text-danger-700 text-xs font-medium rounded">
                                {cat.vat_rate_display}
                              </span>
                              <span className="text-sm text-slate-600">
                                ({cat.count} εγγρ.)
                              </span>
                            </div>
                            <span className="font-semibold text-danger-600">
                              {formatCurrency(cat.vat_amount)}
                            </span>
                          </div>
                        ))}
                      </div>
                    ) : (
                      <p className="text-slate-400 text-center py-4">Δεν υπάρχουν εγγραφές</p>
                    )}
                  </div>
                </div>
              </div>
            </>
          )}
        </div>
      ) : activeTab === 'calculator' ? (
        /* Calculator Tab */
        <VATPeriodCalculator />
      ) : (
        /* Invoices Tab — αποστολή στο myDATA */
        <MyDataInvoices />
      )}
    </div>
  );
}
